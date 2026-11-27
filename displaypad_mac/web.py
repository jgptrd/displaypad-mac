"""Local configurator and MCP endpoint: a small HTTP server inside the service.

Security: binds to 127.0.0.1 only; the Host header must be 127.0.0.1/localhost so
a DNS-rebinding page cannot reach it.
- /api/*: the browser UI. Every call must carry the secret token (X-Token header)
  that the launcher passes in the URL. Without it, any website could POST a
  "shell" action through the browser.
- /pad: the floating pad (popup.py), shown by the DisplayPad app. Same token as the configurator.
- /mcp: the MCP server for AI assistants (see mcp.py). Off until the user turns it
  on in Settings; needs "Authorization: Bearer <.mcp-token>" and rejects requests
  that a web page sends (Origin header from another site).
"""

import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PIL import Image

from . import anim, browsers, daemon, emojidata, i18n, keycapture, live, macos, macro, mcp, obs, presets, sound  # daemon: circular, used at call time only
from .actions import run_actions, test_actions
from .i18n import t
from .render import MAX_CORNER, effect_of, effect_preview, frame_durations, render_key

log = logging.getLogger(__name__)

PORT = int(os.environ.get("DISPLAYPAD_PORT", "8765"))
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
_page_cache = {}


def _page(name: str = "index.html"):
    """index.html (or pad.html), with a short hash of it written in. An open configurator
    compares its hash with the one in /api/status and reloads itself after an update: an old
    page would keep talking to the new service the old way. The floating pad does the same
    with /api/pad."""
    path = os.path.join(STATIC, name)
    st = os.stat(path)
    key = (st.st_mtime_ns, st.st_size)
    cache = _page_cache.setdefault(name, {})
    if cache.get("key") != key:
        with open(path, "rb") as f:
            data = f.read()
        build = hashlib.sha1(data).hexdigest()[:12]
        cache.update(key=key, build=build, html=data.replace(b"__PAGE_BUILD__", build.encode(), 1))
    return cache["html"], cache["build"]


def pad_info(svc) -> dict:
    """The pages for the floating pad: each page and folder with its 12 keys (null: empty),
    the page the pad shows (or would show), and the order of the pages. Both pads show the
    same page: the floating pad opens on it and moves it (POST /api/pad/page)."""
    page = svc.popup_page()
    cfg = svc.cfg
    pages = {name: [{k: v for k, v in spec.items() if k != "folder"} if spec else None for spec in keys]
             for name, keys in cfg["pages"].items()}
    page = page if page in pages else cfg["start_page"]
    return {"page": page, "start": cfg["start_page"], "pages": pages,
            "order": [n for n in cfg["pages"] if "/" not in n], "corner": cfg["corner_radius"],
            "language": cfg["language"], "build": _page("pad.html")[1], "rev": svc.config_rev(),
            "update": svc.updates.latest["version"] if svc.updates.available() else None}
MAX_BODY = 12 * 1024 * 1024
APP_DIRS = ("/Applications", "/Applications/Utilities", "/System/Applications",
            "/System/Applications/Utilities", os.path.expanduser("~/Applications"))
SETTINGS_PANES = {
    "input": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
}


def load_token(base_dir: str, name: str = ".token", renew: bool = False) -> str:
    path = os.path.join(base_dir, name)
    if not renew:
        try:
            with open(path) as f:
                tok = f.read().strip()
            if len(tok) >= 32:
                return tok
        except OSError:
            pass
    tok = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(tok)
    return tok


def configurator_url(token: str) -> str:
    return f"http://127.0.0.1:{PORT}/#t={token}"


def mcp_url() -> str:
    return f"http://127.0.0.1:{PORT}/mcp"


def list_apps():
    """Names of the installed apps, also one folder down (Adobe and DaVinci Resolve install
    as /Applications/<Name>/<Name>.app)."""
    names = set()
    for d in APP_DIRS:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for n in entries:
            if n.endswith(".app"):
                names.add(n[:-4])
            elif not n.startswith(".") and os.path.isdir(os.path.join(d, n)):
                try:
                    names.update(s[:-4] for s in os.listdir(os.path.join(d, n)) if s.endswith(".app"))
                except OSError:
                    pass
    return sorted(names, key=str.lower)


IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff"}


def key_image_path(service, rel: str) -> str:
    """The file of a key picture, for the crop editor: only pictures in icons/ or ones
    the configuration already uses, and only image types."""
    base = service.cfg["base_dir"]
    path = os.path.realpath(os.path.join(base, os.path.expanduser(rel or "")))
    icons = os.path.realpath(os.path.join(base, "icons"))
    used = {os.path.realpath(os.path.join(base, os.path.expanduser(s["image"])))
            for slots in service.cfg["pages"].values() for s in slots if s and s.get("image")}
    if not (path.startswith(icons + os.sep) or path in used):
        raise PermissionError(t("that picture is not part of the configuration"))
    if os.path.splitext(path)[1].lower() not in IMAGE_TYPES or not os.path.isfile(path):
        raise FileNotFoundError(t("picture not found: {path}", path=rel))
    return path


def save_upload(data: bytes, base_dir: str) -> str:
    """Store an uploaded picture under icons/: stills as PNG, animations
    (GIF, WebP, APNG, Lottie .json/.lottie/.tgs) as animated WebP."""
    icons = os.path.join(base_dir, "icons")
    os.makedirs(icons, exist_ok=True)
    stem = "icono-" + secrets.token_hex(4)
    lottie = anim.lottie_json(data)
    if lottie is not None:
        info = anim.convert_lottie(lottie, os.path.join(icons, stem + ".webp"))
        log.info("Lottie saved as %s.webp (%d frames, %d ms)", stem, info["frames"], info["ms"])
        return f"icons/{stem}.webp"
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise ValueError(t("the file is not a valid image or animation "
                           "(use PNG, JPG, GIF, WebP or Lottie .json / .lottie / .tgs)"))
    if getattr(img, "n_frames", 1) > 1:
        frames = anim.read_frames(img, upload=True)
        anim.save_webp(frames, os.path.join(icons, stem + ".webp"))
        log.info("animation saved as %s.webp (%d frames)", stem, len(frames))
        return f"icons/{stem}.webp"
    # 3x the key size on the shorter side is plenty, also once a wide picture is cropped to a square
    img = anim.limit_size(img.convert("RGBA"), 306, 4 * 306)
    img.save(os.path.join(icons, stem + ".png"))
    return f"icons/{stem}.png"


class _Handler(BaseHTTPRequestHandler):
    service = None  # set by start()
    token = ""
    server_version = "DisplayPadMac"

    def log_message(self, fmt, *args):
        log.debug("web: " + fmt, *args)

    # ------------------------------------------------------------ helpers
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _origin_ok(self) -> bool:
        origin = (self.headers.get("Origin") or "").lower()
        return origin in ("", "null", f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    def _auth_ok(self) -> bool:
        return hmac.compare_digest(self.headers.get("X-Token", ""), self.token)

    def _send(self, code: int, body: bytes, ctype: str, headers: dict = None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, str(v))
        if body or code != 202:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200, headers: dict = None):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", headers)

    def _body(self, limit: int = MAX_BODY) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError(t("file too large (12 MB max)") if limit == MAX_BODY
                             else t("the sound is too large (50 MB max)"))
        return self.rfile.read(n)

    def _guard(self) -> bool:
        if not self._host_ok():
            self._send(403, b"forbidden", "text/plain")
            return False
        if urlparse(self.path).path.startswith("/api/") and not self._auth_ok():
            self._json({"error": t("invalid key: open the configurator from the DisplayPad app")}, 401)
            return False
        return True

    def _mcp_info(self) -> dict:
        svc = self.service
        base = svc.cfg["base_dir"]
        bridge = os.path.join(base, "displaypad-mcp")
        return {"url": mcp_url(), "token": svc.mcp_token, "bridge": bridge,
                "bridge_installed": os.access(bridge, os.X_OK), "enabled": svc.cfg["mcp"]["enabled"]}

    # ------------------------------------------------------------ MCP (AI assistants)
    def _mcp_error(self, code: int, message: str):
        self._json({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": message}}, code)

    def _mcp(self, method: str):
        svc = self.service
        if not self._host_ok() or not self._origin_ok():
            return self._send(403, b"forbidden", "text/plain")
        if method != "POST":  # no server-to-client stream: every answer comes back on the POST
            return self._send(405, b"method not allowed", "text/plain", {"Allow": "POST"})
        if not svc.cfg["mcp"]["enabled"]:
            return self._mcp_error(403, "AI assistants are turned off: turn on \"Allow AI assistants to connect\" "
                                        "in the DisplayPad app, Settings > AI assistants")
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + svc.mcp_token):
            return self._mcp_error(401, "missing or wrong access key: copy it from the DisplayPad app, "
                                        "Settings > AI assistants (header \"Authorization: Bearer <key>\")")
        try:
            msg = json.loads(self._body() or b"null")
        except ValueError as e:
            return self._json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}}, 400)
        with i18n.override("en"):  # assistants get English, whatever the UI language
            if isinstance(msg, list):  # JSON-RPC batch (protocol 2025-03-26)
                out = [r for r in (mcp.handle(m, svc) for m in msg) if r is not None]
            else:
                out = mcp.handle(msg, svc)
        if not out:
            return self._send(202, b"", "")
        self._json(out)

    # ------------------------------------------------------------ routes
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/mcp":
            return self._mcp("GET")
        if not self._guard():
            return
        svc = self.service
        if path in ("/", "/index.html"):
            self._send(200, _page()[0], "text/html; charset=utf-8")
        elif path == "/pad":  # the floating pad, in the DisplayPad app
            self._send(200, _page("pad.html")[0], "text/html; charset=utf-8")
        elif path == "/api/pad":
            self._json(pad_info(svc))
        elif path == "/api/pad/state":  # the open floating pad follows the pad and the app pages
            self._json({"page": svc.page, "rev": svc.config_rev()})
        elif path == "/api/popup/wait":  # the DisplayPad app, waiting to show the floating pad
            q = parse_qs(urlparse(self.path).query)
            try:
                seen = int(q.get("rev", ["-1"])[0])
            except ValueError:
                seen = -1
            report = {"hotkey": q["hotkey"][0][:40]} if "hotkey" in q else {}
            self._json(svc.popup.wait(seen, report))
        elif path == "/api/config":
            try:
                with open(svc.config_path, "rb") as f:
                    data = f.read()
                rev = svc.config_rev()
                self._json(json.loads(data), headers={"X-Config-Rev": rev})
            except (OSError, ValueError) as e:
                self._json({"error": t("could not read config.json: {error}", error=e)}, 500)
        elif path == "/api/update":  # a newer version on GitHub? (Settings > About)
            self._json(svc.updates.status(notes=True))
        elif path == "/api/status":
            st = svc.status()
            st["page_build"] = _page()[1]
            self._json(st)
        elif path == "/api/apps":
            self._json(list_apps())
        elif path == "/api/browsers":  # the browsers on this Mac and the default one, for "open" actions
            self._json(browsers.installed(fresh=True))
        elif path == "/api/presets":  # ready-made pages for popular apps, in the page's language
            lang = parse_qs(urlparse(self.path).query).get("lang", ["en"])[0]
            self._json(presets.catalog("es" if lang == "es" else "en", list_apps()))
        elif path == "/api/emoji":  # the Mac's emoji and their names, for the emoji picker
            lang = parse_qs(urlparse(self.path).query).get("lang", ["en"])[0]
            self._json(emojidata.catalog("es" if lang == "es" else "en"))
        elif path == "/api/mcp":
            self._json(self._mcp_info())
        elif path == "/api/obs":  # the connection, without the password
            self._json(obs.public(obs.load_settings(self.service.cfg["base_dir"])))
        elif path == "/api/obs/info":  # asks OBS: its scenes and sources, or why it can't be reached
            self._json(obs.info(self.service.cfg["base_dir"]))
        elif path == "/api/sounds":  # the sounds added here and the Mac's own, for the sound picker
            self._json(sound.list_sounds(svc.cfg["base_dir"]))
        elif path == "/api/macro/record":
            self._json(macro.recorder.status())
        elif path == "/api/keys/capture":  # polled by the page while it records: stops when it stops
            self._json(keycapture.capture.status())
        elif path == "/api/image":  # the original picture of a key, for the crop editor
            rel = parse_qs(urlparse(self.path).query).get("path", [""])[0]
            try:
                file = key_image_path(svc, rel)
            except PermissionError as e:
                return self._json({"error": str(e)}, 403)
            except FileNotFoundError as e:
                return self._json({"error": str(e)}, 404)
            with open(file, "rb") as f:
                self._send(200, f.read(), IMAGE_TYPES[os.path.splitext(file)[1].lower()])
        else:
            self._send(404, b"not found", "text/plain")

    def do_DELETE(self):
        if urlparse(self.path).path == "/mcp":
            return self._mcp("DELETE")
        self._send(405, b"method not allowed", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/mcp":
            return self._mcp("POST")
        if not self._guard():
            return
        svc = self.service
        try:
            if path == "/api/render":
                spec = json.loads(self._body() or b"{}") or None
                base = svc.cfg["base_dir"]
                query = parse_qs(urlparse(self.path).query)
                try:  # the page says which corners it shows (the setting may be changing)
                    corner = max(0, min(MAX_CORNER, int(query["corner"][0])))
                except (KeyError, ValueError):
                    corner = svc.cfg["corner_radius"]
                lv = svc.live.face(spec) if spec and "live" in spec else None  # a live key: what it shows now
                if query.get("first"):  # quick still, e.g. while cropping
                    buf = io.BytesIO()
                    render_key(spec, base, first_only=True, corner=corner, live=lv).save(buf, "PNG")
                    return self._send(200, buf.getvalue(), "image/png")
                if query.get("effect"):  # the press effect played once ("Try it")
                    if not effect_of(spec):
                        return self._json({"error": t("this key has no press effect")}, 400)
                    frames, durs = effect_preview(spec, base, corner, lv)
                    buf = io.BytesIO()
                    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=durs,
                                   loop=1, lossless=True, quality=0, method=0)
                    return self._send(200, buf.getvalue(), "image/webp",
                                      {"X-Frames": len(durs), "X-Duration": sum(durs)})
                durs = None if lv and lv["style"] == "meter" else frame_durations(spec, base)
                buf = io.BytesIO()
                if durs:  # animated preview, frame for frame what the pad shows
                    frames = [render_key(spec, base, frame=i, corner=corner, live=lv) for i in range(len(durs))]
                    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=durs,
                                   loop=0, lossless=True, quality=0, method=0)
                    self._send(200, buf.getvalue(), "image/webp",
                               {"X-Frames": len(durs), "X-Duration": sum(durs)})
                else:
                    render_key(spec, base, corner=corner, live=lv).save(buf, "PNG")
                    self._send(200, buf.getvalue(), "image/png")
            elif path == "/api/live":  # the live keys the page shows: keeps their readings going, says when they change
                body = json.loads(self._body() or b"{}") or {}
                looks = [k for k in (body.get("keys") or [])[:200] if isinstance(k, dict)]
                who = "popup" if body.get("who") == "popup" else "portal"  # the floating pad, or the configurator
                svc.live.watch(who, [k.get("live") for k in looks], ttl=live.LOOKER_TTL)
                faces = [svc.live.face(k) if "live" in k else None for k in looks]
                self._json({"sigs": [f["sig"] if f else "" for f in faces]})
            elif path == "/api/upload":
                self._json({"path": save_upload(self._body(), svc.cfg["base_dir"])})
            elif path == "/api/sound":  # ?name=<the file's name>, the file in the body
                name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
                self._json(sound.save_upload(self._body(sound.MAX_UPLOAD), name, svc.cfg["base_dir"]))
            elif path == "/api/sound/stop":
                self._json({"stopped": sound.stop_all()})
            elif path == "/api/test":
                body = json.loads(self._body())
                pages = (body.get("pages") or svc.cfg["pages"])
                self._json(test_actions(body.get("spec") or {}, svc, pages))
            elif path == "/api/pad/press":  # a key clicked on the floating pad: {page, key (1-12)}
                body = json.loads(self._body() or b"{}")
                keys = svc.cfg["pages"].get(body.get("page"))
                n = body.get("key")
                if keys is None or not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(keys):
                    return self._json({"error": t("that key is not on the pad any more")}, 400)
                spec = keys[n - 1]
                if spec:
                    log.info("key %d pressed on '%s' (floating pad)", n, body["page"])
                    threading.Thread(target=run_actions, args=(spec, svc), daemon=True).start()
                self._json({"ok": bool(spec)})
            elif path == "/api/pad/page":  # the floating pad moved: {to: a page, a folder, "back" or "up"}
                to = json.loads(self._body() or b"{}").get("to")
                if not isinstance(to, str) or not (to in ("back", "up") or to in svc.cfg["pages"]):
                    return self._json({"error": t("that page is not on the pad any more")}, 400)
                log.info("floating pad: page '%s'", to)
                svc.request_page(to)  # the pad on the desk follows
                self._json({"page": svc.wait_page()})
            elif path == "/api/popup/show":  # "Try it" in Settings
                svc.popup.show("test")
                self._json(svc.popup.status())
            elif path == "/api/settings":
                self._json({"rev": svc.update_settings(json.loads(self._body() or b"{}"))})
            elif path == "/api/obs":  # {host, port, password}; no password: keep the saved one
                self._json(obs.save_settings(svc.cfg["base_dir"], json.loads(self._body() or b"{}")))
            elif path == "/api/mcp/token":
                svc.mcp_token = load_token(svc.cfg["base_dir"], ".mcp-token", renew=True)
                log.info("new MCP access key created")
                self._json(self._mcp_info())
            elif path == "/api/show-page":
                page = json.loads(self._body()).get("page")
                if page in svc.cfg["pages"]:
                    svc.request_page(page)
                self._json({"ok": True})
            elif path == "/api/permissions":
                which = json.loads(self._body() or b"{}").get("which")
                if which == "input":
                    macos.request_input_monitoring()
                elif which == "accessibility":
                    macos.request_post_events()
                if which in SETTINGS_PANES:
                    subprocess.Popen(["open", SETTINGS_PANES[which]])
                self._json(svc.status())
            elif path == "/api/macro/record":  # options: {"keys", "mouse", "moves"}
                macro.recorder.start(json.loads(self._body() or b"{}"))
                self._json(macro.recorder.status())
            elif path == "/api/macro/record/stop":
                macro.recorder.stop("button")
                self._json(macro.recorder.status())
            elif path == "/api/macro/record/cancel":
                macro.recorder.cancel()
                self._json(macro.recorder.status())
            elif path == "/api/keys/capture":  # take the keyboard until one shortcut is pressed ({"mouse": true}: or a mouse button)
                self._json(keycapture.capture.start(mouse=bool((json.loads(self._body() or b"{}") or {}).get("mouse"))))
            elif path == "/api/keys/capture/cancel":
                self._json(keycapture.capture.cancel())
            elif path == "/api/macro/stop-all":
                self._json({"stopped": macro.stop_all()})
            elif path == "/api/update/check":
                self._json(svc.updates.check_now())
            elif path == "/api/update/install":  # downloads the latest release and runs its install.sh
                svc.updates.install()
                self._json(svc.updates.status(notes=True))
            elif path == "/api/restart":
                # launchd (KeepAlive) starts the service again; needed after granting a permission
                self._json({"ok": True})
                threading.Timer(0.3, svc.stop).start()
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            log.warning("web %s failed: %s", path, e)
            self._json({"error": str(e)}, 400)

    def do_PUT(self):
        if not self._guard():
            return
        if urlparse(self.path).path != "/api/config":
            self._send(404, b"not found", "text/plain")
            return
        try:
            raw = json.loads(self._body())
            rev = self.service.save_config(raw, self.headers.get("X-Config-Rev", ""))
            self._json({"ok": True, "rev": rev})
        except daemon.ConfigConflict as e:
            self._json({"error": str(e), "conflict": True}, 409)
        except Exception as e:
            self._json({"error": str(e)}, 400)


def start(service, token: str):
    handler = type("Handler", (_Handler,), {"service": service, "token": token})
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    except OSError as e:
        log.error("configurator could not listen on 127.0.0.1:%d: %s", PORT, e)
        return None
    threading.Thread(target=httpd.serve_forever, daemon=True, name="configurator").start()
    log.info("configurator on http://127.0.0.1:%d", PORT)
    return httpd
