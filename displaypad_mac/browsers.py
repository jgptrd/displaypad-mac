"""Web addresses in the browser of your choice: a new tab, a new window, or the tab already open.

  {"type": "open", "target": "https://web.whatsapp.com", "browser": "Google Chrome",
   "new": "tab" | "window", "reuse_tab": true}

"browser" is the browser app's name (as list_apps gives it); without it the Mac's default
browser opens the address. "new" is "tab" (default) or "window". With "reuse_tab", when a tab
of that browser already shows the address, that tab and its window come to the front instead
of a new one opening: a tab matches when its address starts with the key's, ignoring http or
https, "www." and anything after "#", so "https://web.whatsapp.com" finds any WhatsApp tab.

Safari and the Chromium browsers (Chrome, Edge, Brave, Vivaldi, Chromium) can do all of it;
other browsers (Firefox, Arc, Opera...) get the address the way they take any link, usually in
a new tab. Looking at tabs and making windows uses Apple Events, so the first time macOS asks
whether DisplayPad may control the browser (Privacy & Security > Automation).
"""

import ctypes
import ctypes.util
import json
import logging
import os
import re
import subprocess
import threading
import time
import urllib.parse
from typing import Optional

from .i18n import t

log = logging.getLogger(__name__)

NEW = ("tab", "window")
SAFARI = {"com.apple.safari", "com.apple.safaritechnologypreview"}
CHROMIUM = {"com.google.chrome", "com.google.chrome.beta", "com.google.chrome.dev", "com.google.chrome.canary",
            "org.chromium.chromium", "com.microsoft.edgemac", "com.microsoft.edgemac.beta",
            "com.microsoft.edgemac.dev", "com.microsoft.edgemac.canary", "com.brave.browser",
            "com.brave.browser.beta", "com.brave.browser.nightly", "com.vivaldi.vivaldi"}
WEB = re.compile(r"^https?://", re.I)

# The windows of a running browser, front to back: their id, the active tab and every tab's address.
TABS_JS = """function run(argv) {
  const app = Application(argv[0]);
  if (!app.running()) return "null";
  const safari = argv[1] === "safari", out = [];
  for (const w of app.windows()) {
    try { out.push({id: w.id(), active: safari ? w.currentTab.index() : w.activeTabIndex(), tabs: w.tabs.url()}); }
    catch (e) {}  // not a browser window (Safari's Settings) or it just closed
  }
  return JSON.stringify(out);
}"""
# Bring one tab and its window to the front.
FOCUS_JS = """function run(argv) {
  const app = Application(argv[0]), w = app.windows.byId(JSON.parse(argv[2])), i = Number(argv[3]);
  if (argv[1] === "safari") { w.currentTab = w.tabs[i - 1]; if (w.miniaturized()) w.miniaturized = false; }
  else { w.activeTabIndex = i; if (w.minimized()) w.minimized = false; }
  w.index = 1;
  app.activate();
  return "ok";
}"""
# A new window with the address, if the browser is running (else opening it makes one).
WINDOW_JS = """function run(argv) {
  const app = Application(argv[0]);
  if (!app.running()) return "not running";
  if (argv[1] === "safari") app.Document({url: argv[2]}).make();
  else app.Window().make().activeTab.url = argv[2];
  app.activate();
  return "ok";
}"""

_ls = None
_cache = {"t": 0.0, "list": None}
_lock = threading.Lock()


def _services():
    """LaunchServices through ctypes (no PyObjC): who opens https:// links."""
    global _ls
    if _ls is None:
        vp = ctypes.c_void_p
        cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        cs = ctypes.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
        cf.CFStringCreateWithCString.restype = vp
        cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [vp]
        cf.CFArrayGetValueAtIndex.restype = vp
        cf.CFArrayGetValueAtIndex.argtypes = [vp, ctypes.c_long]
        cf.CFURLGetFileSystemRepresentation.restype = ctypes.c_bool
        cf.CFURLGetFileSystemRepresentation.argtypes = [vp, ctypes.c_bool, ctypes.c_char_p, ctypes.c_long]
        cf.CFRelease.argtypes = [vp]
        for fn in ("LSCopyDefaultHandlerForURLScheme", "LSCopyAllHandlersForURLScheme"):
            getattr(cs, fn).restype = vp
            getattr(cs, fn).argtypes = [vp]
        cs.LSCopyApplicationURLsForBundleIdentifier.restype = vp
        cs.LSCopyApplicationURLsForBundleIdentifier.argtypes = [vp, vp]
        _ls = (cf, cs)
    return _ls


def _cf_text(cf, ref) -> str:
    buf = ctypes.create_string_buffer(1024)
    return buf.value.decode() if ref and cf.CFStringGetCString(ref, buf, 1024, 0x08000100) else ""


def _app_path(cf, cs, bundle_id: str) -> str:
    """Where an app is, skipping copies in hidden folders (test builds, caches) and the Trash."""
    s = cf.CFStringCreateWithCString(None, bundle_id.encode(), 0x08000100)
    urls = cs.LSCopyApplicationURLsForBundleIdentifier(s, None)
    cf.CFRelease(s)
    found = ""
    if urls:
        for i in range(cf.CFArrayGetCount(urls)):
            buf = ctypes.create_string_buffer(4096)
            if cf.CFURLGetFileSystemRepresentation(cf.CFArrayGetValueAtIndex(urls, i), True, buf, 4096):
                p = buf.value.decode()
                if not any(part.startswith(".") for part in p.split("/")):
                    found = p
                    break
        cf.CFRelease(urls)
    return found


def _info(bundle_id: str, path: str) -> dict:
    return {"name": os.path.basename(path)[:-4] if path.endswith(".app") else os.path.basename(path),
            "id": bundle_id, "tabs": family(bundle_id) is not None}


def family(bundle_id: str) -> Optional[str]:
    """"safari" or "chromium" for the browsers that can pick a window or find a tab, else None."""
    b = (bundle_id or "").lower()
    return "safari" if b in SAFARI else "chromium" if b in CHROMIUM else None


def installed(fresh: bool = False) -> dict:
    """The browsers on this Mac (the apps that open https:// links) and which one is the default."""
    with _lock:
        if not fresh and _cache["list"] and time.monotonic() - _cache["t"] < 30:
            return _cache["list"]
        cf, cs = _services()
        https = cf.CFStringCreateWithCString(None, b"https", 0x08000100)
        default_ref = cs.LSCopyDefaultHandlerForURLScheme(https)
        default_id = _cf_text(cf, default_ref)
        if default_ref:
            cf.CFRelease(default_ref)
        ids = []
        arr = cs.LSCopyAllHandlersForURLScheme(https)
        if arr:
            ids = [_cf_text(cf, cf.CFArrayGetValueAtIndex(arr, i)) for i in range(cf.CFArrayGetCount(arr))]
            cf.CFRelease(arr)
        cf.CFRelease(https)
        out, default = [], None
        for bid in ids:
            path = _app_path(cf, cs, bid) if bid else ""
            if not path:
                continue
            b = _info(bid, path)
            if bid.lower() == default_id.lower():
                default = b
            if all(x["name"] != b["name"] for x in out):
                out.append(b)
        if not default and default_id:
            path = _app_path(cf, cs, default_id)
            default = _info(default_id, path) if path else None
        out.sort(key=lambda b: b["name"].lower())
        _cache.update(t=time.monotonic(), list={"default": default, "browsers": out})
        return _cache["list"]


def find(name: str) -> Optional[dict]:
    """A browser by its app name ("Google Chrome", "Safari.app") or bundle id."""
    want = re.sub(r"\.app$", "", str(name or "").strip(), flags=re.I).lower()
    if not want:
        return None
    for b in installed()["browsers"]:
        if want in (b["name"].lower(), b["id"].lower()):
            return b
    return None


def validate(action: dict) -> str:
    if "browser" in action and (not isinstance(action["browser"], str) or not action["browser"].strip()):
        return t("browser must be the name of a browser app, such as Safari or Google Chrome")
    if action.get("new", "tab") not in NEW:
        return t("new must be tab or window")
    if action.get("reuse_tab") not in (None, True, False):
        return t("reuse_tab must be true or false")
    return ""


def _key(url) -> Optional[str]:
    """An address as tabs are compared: no scheme, no "www.", no "#..." part."""
    try:
        u = urllib.parse.urlsplit(str(url or "").strip())
        port = u.port
    except ValueError:
        return None
    if u.scheme.lower() not in ("http", "https") or not u.hostname:
        return None
    host = u.hostname[4:] if u.hostname.startswith("www.") else u.hostname
    return host + (f":{port}" if port and port not in (80, 443) else "") + (u.path or "/") + \
        ("?" + u.query if u.query else "")


def same_page(tab_url, target) -> bool:
    """True when a tab shows the target address or a page under it."""
    tab, want = _key(tab_url), _key(target)
    if not tab or not want:
        return False
    want = want.rstrip("/")
    return tab.startswith(want) and (len(tab) == len(want) or tab[len(want)] in "/?&" or want[-1] in "?&=")


def _jxa(script: str, *args, timeout: float = 30) -> str:
    """Run JavaScript for Automation. The first time, macOS asks the user (that waits here)."""
    r = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", script, *args],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "-1743" in err or "Not authorized" in err:
            raise PermissionError(err)
        raise RuntimeError(err or f"osascript ended with code {r.returncode}")
    return r.stdout.strip()


def _open_with(b: Optional[dict], url: str):
    cmd = ["open", "-b", b["id"], url] if b else ["open", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or t("could not open {url}", url=url))


def find_tab(b: dict, url: str) -> Optional[tuple]:
    """(window id, tab number) of a tab showing url in a running browser, front window first."""
    fam = family(b["id"])
    out = _jxa(TABS_JS, b["id"], fam)
    for w in json.loads(out) or []:
        tabs = w.get("tabs") or []
        order = [w.get("active", 1)] + [i for i in range(1, len(tabs) + 1) if i != w.get("active")]
        for i in order:
            if 1 <= i <= len(tabs) and same_page(tabs[i - 1], url):
                return w["id"], i
    return None


def open_url(url: str, browser: str = "", new: str = "tab", reuse: bool = False) -> str:
    """Open a web address as an "open" action asks; returns what happened, for the Test button."""
    if not browser and new == "tab" and not reuse:
        _open_with(None, url)  # as before: the Mac's default browser takes it
        return ""
    b, notes = find(browser) if browser else installed()["default"], []
    if browser and not b:
        notes.append(t("{browser} is not installed, so the default browser opened it", browser=browser))
        b = installed()["default"]
    if not b:
        _open_with(None, url)
        return ". ".join(notes)
    name, fam = b["name"], family(b["id"])
    if (reuse or new == "window") and not fam:
        notes.append(t("{browser} can't be asked for its tabs or a new window, so it opened the address "
                       "the way it opens links", browser=name))
    try:
        if reuse and fam:
            hit = find_tab(b, url)
            if hit:
                _jxa(FOCUS_JS, b["id"], fam, json.dumps(hit[0]), str(hit[1]))
                log.info("went to the %s tab showing %s", name, url)
                return ". ".join([t("went to the {browser} tab already showing it", browser=name)] + notes)
        if new == "window" and fam and _jxa(WINDOW_JS, b["id"], fam, url) == "ok":
            return ". ".join([t("opened in a new {browser} window", browser=name)] + notes)
    except PermissionError:
        notes.append(t("to find open tabs or make windows, allow DisplayPad to control {browser} in System "
                       "Settings > Privacy & Security > Automation", browser=name))
        log.warning("not allowed to control %s; opening %s in a tab", name, url)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError) as e:
        log.warning("%s: %s; opening %s in a tab", name, e, url)
    _open_with(b, url)
    return ". ".join([t("opened in {browser}", browser=name)] + notes)


def is_web(target) -> bool:
    return bool(WEB.match(str(target or "").strip()))
