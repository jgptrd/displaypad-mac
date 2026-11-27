"""New versions: the service asks GitHub for the latest release now and then; the configurator
offers it (and the floating pad and the DisplayPad app say there is one). Installing it
downloads the release's zip and runs its install.sh, the same as updating by hand: the
configuration is kept.

What is sent: one request for https://api.github.com/repos/<repo>/releases/latest, with a
User-Agent naming DisplayPadMac and its version, and nothing about the Mac or the person.
A minute after the service starts, then every 6 hours. Off with "check_updates": false
(Settings > About); "Check now" still works then.

Publishing a version (see docs/GUIDE.md, "Updates"): __version__ in __init__.py, a tag
"v<version>" and a GitHub release for it with the zip from `git archive` attached
(displaypad-mac-v<version>.zip, everything in a displaypad-mac/ folder). Without the zip,
GitHub's own zip of the tag is used.
"""

import json
import logging
import os
import re
import shlex
import shutil
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Optional

from . import __version__, popup
from .i18n import t

log = logging.getLogger(__name__)

REPO = os.environ.get("DISPLAYPAD_UPDATE_REPO", "jgptrd/displaypad-mac")
API = os.environ.get("DISPLAYPAD_UPDATE_API", "https://api.github.com")  # tests: a local server
FIRST_CHECK = 60.0        # seconds after the service starts: at login the network may not be up yet
EVERY = 6 * 3600.0
RETRY = 30 * 60.0         # after a check that failed (offline)
TIMEOUT = 15
MAX_ZIP = 60 * 1024 * 1024
HOSTS = ("github.com", "githubusercontent.com")  # where a release's zip may come from
WORK = os.path.expanduser("~/Library/Caches/DisplayPadMac")
LOG = os.path.expanduser("~/Library/Logs/DisplayPadMac-update.log")
# launchd gives the service a short PATH; install.sh needs Homebrew's Python (and brew)
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def version_of(text) -> Optional[tuple]:
    """'v1.4.0' / '1.4' -> (1, 4, 0); None when it isn't a version."""
    m = re.match(r"\s*v?(\d+)\.(\d+)(?:\.(\d+))?\s*$", str(text or ""))
    return tuple(int(x or 0) for x in m.groups()) if m else None


def _get(url: str, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": f"DisplayPadMac/{__version__}", **(headers or {})})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _trusted(url: str) -> bool:
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    return (u.scheme == "https" and any(host == h or host.endswith("." + h) for h in HOSTS)) or url.startswith(API)


class Updater:
    def __init__(self, svc):
        self.svc = svc
        self.latest: Optional[dict] = None  # the newest release: version, name, notes, url, zip
        self.checked: Optional[float] = None  # when GitHub last answered (time.time())
        self.error = ""
        self.state = "idle"                 # checking, downloading, installing, failed
        self.message = ""
        self._etag = ""
        self._lock = threading.Lock()
        self._kick = threading.Event()
        # installed by the Update button: what it left behind is still there (the configurator says so once)
        self.just_updated = __version__ if os.path.isdir(os.path.join(WORK, "update-" + __version__)) else None

    # ------------------------------------------------------------ checking
    def start(self):
        threading.Thread(target=self._run, name="updates", daemon=True).start()

    def _run(self):
        delay, tidy = FIRST_CHECK, True
        while not self.svc._stop.is_set():
            asked = self._kick.wait(delay)
            self._kick.clear()
            if self.svc._stop.is_set():
                return
            if tidy:  # the downloads of earlier updates (install.sh is done with them by now)
                tidy = False
                for name in os.listdir(WORK) if os.path.isdir(WORK) else []:
                    if name.startswith("update-") and self.state not in ("downloading", "installing"):
                        shutil.rmtree(os.path.join(WORK, name), ignore_errors=True)
            if not asked and not self.svc.cfg.get("check_updates", True):
                delay = EVERY
                continue
            delay = EVERY if self.check() else RETRY

    def check(self) -> bool:
        """Asks GitHub for the latest release. False when it couldn't (offline...)."""
        with self._lock:
            if self.state in ("downloading", "installing"):
                return True
            self.state = "checking"
        try:
            headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
            if self._etag and self.latest:
                headers["If-None-Match"] = self._etag  # unchanged: GitHub answers 304, which doesn't count against its limit
            try:
                with _get(f"{API}/repos/{REPO}/releases/latest", headers) as r:
                    rel, etag = json.load(r), r.headers.get("ETag", "")
            except urllib.error.HTTPError as e:
                if e.code == 304:
                    self.checked, self.error = time.time(), ""
                    return True
                if e.code == 404:  # no release yet
                    self.latest, self.checked, self.error = None, time.time(), ""
                    return True
                raise
            ver = version_of(rel.get("tag_name"))
            if not ver:
                raise ValueError(t("the latest release has no version number ({tag})", tag=rel.get("tag_name")))
            zips = [a for a in rel.get("assets") or [] if str(a.get("name", "")).endswith(".zip")]
            latest = {"version": ".".join(map(str, ver)), "name": rel.get("name") or rel.get("tag_name"),
                      "notes": str(rel.get("body") or "")[:6000], "url": rel.get("html_url") or "",
                      "published": rel.get("published_at") or "",
                      "zip": zips[0]["browser_download_url"] if zips else rel.get("zipball_url") or ""}
            new = self.latest is None or latest["version"] != self.latest["version"]
            self.latest, self._etag, self.checked, self.error = latest, etag, time.time(), ""
            if new and self.available():
                log.info("update: DisplayPad %s is available (this is %s)", latest["version"], __version__)
            return True
        except Exception as e:
            self.error = str(getattr(e, "reason", None) or e)
            log.warning("update: could not check for a new version: %s", self.error)
            return False
        finally:
            with self._lock:
                if self.state == "checking":
                    self.state = "idle"

    def check_now(self) -> dict:
        self.check()
        return self.status(notes=True)

    def available(self) -> bool:
        return bool(self.latest and version_of(self.latest["version"]) > version_of(__version__))

    def status(self, notes: bool = False) -> dict:
        lt = self.latest or {}
        out = {"current": __version__, "latest": lt.get("version"), "available": self.available(),
               "name": lt.get("name"), "url": lt.get("url") or f"https://github.com/{REPO}/releases",
               "checked": self.checked, "error": self.error, "state": self.state, "message": self.message,
               "auto": bool(self.svc.cfg.get("check_updates", True)), "log": LOG,
               "just_updated": self.just_updated}
        if notes:
            out["notes"] = lt.get("notes", "")
        return out

    # ------------------------------------------------------------ installing
    def install(self):
        """Downloads the latest release and installs it, in the background. The service
        restarts at the end (install.sh replaces it), then the configurator opens again."""
        with self._lock:
            if self.state in ("downloading", "installing"):
                raise ValueError(t("the update is already being installed"))
            if not self.available():
                raise ValueError(t("there is no newer version to install"))
            if not _trusted(self.latest["zip"]):
                raise ValueError(t("the release's zip is not on GitHub: {url}", url=self.latest["zip"]))
            self.state, self.message = "downloading", ""
        threading.Thread(target=self._install, args=(dict(self.latest),), name="update", daemon=True).start()

    def _install(self, rel: dict):
        work = os.path.join(WORK, "update-" + rel["version"])
        try:
            shutil.rmtree(work, ignore_errors=True)
            os.makedirs(work)
            archive = os.path.join(work, "release.zip")
            log.info("update: downloading DisplayPad %s", rel["version"])
            self._download(rel["zip"], archive)
            src = unpack(archive, os.path.join(work, "src"))
            found = _version_in(src)
            if found != rel["version"]:
                raise ValueError(t("the download is version {found}, not {version}", found=found or "?",
                                   version=rel["version"]))
            self.state = "installing"
            log.info("update: installing DisplayPad %s; the service restarts (details in %s)", rel["version"], LOG)
            proc = run_installer(src, __version__, rel["version"])
            code = proc.wait()  # install.sh stops this service near the end: usually it never gets here
            if code != 0:
                raise RuntimeError(t("install.sh stopped with an error (code {code}); see {log}", code=code, log=LOG))
            self.state = "idle"
        except Exception as e:
            log.warning("update: %s", e)
            self.state, self.message = "failed", str(e)

    def _download(self, url: str, path: str):
        with _get(url) as r, open(path, "wb") as f:
            if not _trusted(r.geturl()):  # where the redirects ended up
                raise ValueError(t("the release's zip is not on GitHub: {url}", url=r.geturl()))
            size = int(r.headers.get("Content-Length") or 0)
            if size > MAX_ZIP:
                raise ValueError(t("the download is too big ({mb} MB)", mb=size // 2**20))
            got = 0
            while chunk := r.read(1 << 16):
                got += len(chunk)
                if got > MAX_ZIP:
                    raise ValueError(t("the download is too big ({mb} MB)", mb=got // 2**20))
                f.write(chunk)


def unpack(archive: str, dest: str) -> str:
    """Unzips a release into dest and returns the folder with install.sh in it. Paths that
    would land outside dest, and links, are refused; file modes are kept (install.sh runs
    launcher/build.sh)."""
    root = os.path.realpath(dest)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            mode = info.external_attr >> 16
            target = os.path.realpath(os.path.join(root, info.filename))
            if not target.startswith(root + os.sep) or stat.S_ISLNK(mode):
                raise ValueError(t("the download has an unexpected file: {name}", name=info.filename))
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            if mode & 0o777:
                os.chmod(target, mode & 0o755)
    tops = [os.path.join(root, n) for n in os.listdir(root)]
    for folder in [root] + [p for p in tops if os.path.isdir(p)]:
        if os.path.isfile(os.path.join(folder, "install.sh")) and os.path.isdir(os.path.join(folder, "displaypad_mac")):
            return folder
    raise ValueError(t("the download has no install.sh"))


def _version_in(src: str) -> Optional[str]:
    try:
        with open(os.path.join(src, "displaypad_mac", "__init__.py"), encoding="utf-8") as f:
            m = re.search(r'^__version__ = "([^"]+)"', f.read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def run_installer(src: str, old: str, new: str) -> subprocess.Popen:
    """Runs src/install.sh on its own: in a new session, so it outlives this service when
    install.sh stops it (launchd stops the service's whole process group). Then opens the
    DisplayPad app, which shows the configurator of the new version."""
    q = shlex.quote
    script = (f'export PATH={q(PATH)}:"$PATH"\n'
              f'cd {q(src)} || exit 1\n'
              f'echo "== $(date "+%Y-%m-%d %H:%M:%S") DisplayPadMac {old} -> {new}" >> {q(LOG)}\n'
              f'/bin/zsh ./install.sh >> {q(LOG)} 2>&1 || {{ code=$?; echo "== failed ($code)" >> {q(LOG)}; exit $code; }}\n'
              f'echo "== done" >> {q(LOG)}\n'
              f'sleep 2; open -b {q(popup.APP_ID)} || true  # the configurator, on the new version\n')
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    return subprocess.Popen(["/bin/zsh", "-c", script], cwd=src, start_new_session=True, close_fds=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
