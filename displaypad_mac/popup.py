"""The floating pad: a DisplayPad on the screen, for a Mac without the pad or with it out of reach.

A shortcut brings it up at the mouse; clicking a key runs that key's actions and closes it.
The DisplayPad app (launcher/DisplayPad.swift) shows it and the configurator window; this
side decides when, and runs the keys.

config.json: "popup": {"enabled": true, "trigger": "cmd+middle_click"}. The trigger is
modifiers and then
  - a mouse button: "middle_click", "mouse4" (back) or "mouse5" (forward). An event tap here
    sees it; with the Accessibility permission it holds the click back from the app under the
    mouse (⌘-middle-click opens a link in a new tab in browsers). Without it, the click goes
    through as well.
  - or a key: "ctrl+alt+space". The app registers it as a system hotkey, which needs no
    permission; this side turns the name into a key code and modifiers.

The app keeps one request open (GET /api/popup/wait) and gets "show" when it is time. The
service starts the app in the background when it is not running.
"""

import logging
import os
import subprocess
import threading
import time

from . import keycapture, macos, macro
from .i18n import t

log = logging.getLogger(__name__)

APP_ID = os.environ.get("DISPLAYPAD_APP_ID", "com.displaypadmac.app")
APP_PROCESS = "DisplayPad"
DEFAULT = "cmd+middle_click"
MOUSE = {"middle_click": 2, "mouse4": 3, "mouse5": 4}  # CGMouseButton numbers
_MOUSE_ALIASES = {"middle": "middle_click", "middleclick": "middle_click", "mouse3": "middle_click",
                  "back": "mouse4", "forward": "mouse5"}
_ORDER = ("ctrl", "alt", "shift", "cmd")
_FLAGS = {"ctrl": 0x40000, "alt": 0x80000, "shift": 0x20000, "cmd": 0x100000}  # CGEventFlags
_CARBON = {"cmd": 0x100, "shift": 0x200, "alt": 0x800, "ctrl": 0x1000}       # RegisterEventHotKey
_FLAG_MASK = sum(_FLAGS.values())
_BARE_KEYS = {f"f{i}" for i in range(1, 21)}  # keys that may be a shortcut on their own

EVENT_SECONDS = 3.0    # a "show" waits this long for the app's next request
WAIT_SECONDS = 25.0    # how long the app's request stays open with nothing to say
LAUNCH_EVERY = 60.0    # at most one start of the app this often (a missing app: every 10 min)


def parse(trigger) -> dict:
    """'cmd+middle_click' -> {"trigger": "cmd+middle_click", "kind": "mouse", "button": 2, "flags": ...};
    'ctrl+alt+space' -> {"kind": "key", "code": 49, "carbon": ...}. Raises ValueError."""
    if not isinstance(trigger, str) or not trigger.strip():
        raise ValueError(t("the floating pad needs a shortcut or a mouse button"))
    parts = [p.strip().lower() for p in trigger.replace(" ", "").split("+") if p.strip()]
    *mod_parts, last = parts
    mods = []
    for part in mod_parts:
        name = macos.MOD_ALIASES.get(part, part)
        if name not in macos.MOD_KEYS or name == "fn":
            raise ValueError(t("'{part}' can't be used in the floating pad's shortcut: use ⌘, ⌥, ⌃ or ⇧ and then one key "
                               "or mouse button", part=part))
        name = name[1:] if name.startswith("r") else name  # either side: the system hotkey can't tell them apart
        if name not in mods:
            mods.append(name)
    mods = [m for m in _ORDER if m in mods]
    last = _MOUSE_ALIASES.get(last, last)
    if last in MOUSE:
        return {"trigger": "+".join(mods + [last]), "kind": "mouse", "button": MOUSE[last],
                "flags": sum(_FLAGS[m] for m in mods)}
    if macos.MOD_ALIASES.get(last, last) in macos.MOD_KEYS:
        raise ValueError(t("the floating pad's shortcut needs a key or a mouse button after the modifiers"))
    if last not in macos.KEYCODES:
        raise ValueError(t("unknown key '{key}' in the floating pad's shortcut", key=last))
    if not mods and last not in _BARE_KEYS:
        raise ValueError(t("the floating pad's shortcut needs ⌘, ⌃, ⌥ or ⇧ with that key (F-keys can be alone)"))
    if mods and set(mods) <= {"alt", "shift"}:
        raise ValueError(t("macOS doesn't allow shortcuts with only ⌥ or ⌥⇧: add ⌘ or ⌃"))
    return {"trigger": "+".join(mods + [last]), "kind": "key", "code": macos.KEYCODES[last],
            "carbon": sum(_CARBON[m] for m in mods)}


def settings_of(raw) -> dict:
    """The "popup" object of config.json, checked: {"enabled", "trigger"}. Raises ValueError."""
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ValueError(t("popup must be an object like {\"enabled\": true, \"trigger\": \"cmd+middle_click\"}"))
    unknown = set(raw) - {"enabled", "trigger"}
    if unknown:
        raise ValueError(t("popup: unknown setting '{name}'", name=sorted(unknown)[0]))
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError(t("popup.enabled must be true or false"))
    return {"enabled": enabled, "trigger": parse(raw.get("trigger", DEFAULT))["trigger"]}


class Ctx:
    """What the actions of a floating-pad key see: the service, except that a page switch stays
    in the floating pad (it moves itself) and leaves the pad on the desk alone."""

    def __init__(self, svc):
        self._svc = svc

    def __getattr__(self, name):
        return getattr(self._svc, name)

    def request_page(self, name):
        pass


class MouseTap:
    """An event tap on the extra mouse buttons; calls fire() when the trigger is clicked."""

    def __init__(self, fire):
        self._fire = fire
        self._callback = macro._TAP_CALLBACK(self._on_event)
        self._want = None             # (button, flags)
        self._held = set()            # buttons whose release we hold back too
        self._thread = None
        self._stop = threading.Event()
        self._tap = None
        self.state = "off"            # off | on | listen (the click goes through) | error

    def set(self, want):
        self._want = want
        alive = self._thread is not None and self._thread.is_alive()
        if want and not alive:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stop,), name="popup-mouse", daemon=True)
            self._thread.start()
        elif not want and alive:
            self._stop.set()

    def _run(self, stop):
        tap = src = loop = None
        try:
            mask = (1 << macro._OTHER_DOWN) | (1 << macro._OTHER_UP)
            # active (0) to hold the click back; listen-only (1) without Accessibility
            for option in ((0, 1) if macos.post_events_allowed() else (1,)):
                tap = macro._cg.CGEventTapCreate(1, 0, option, mask, self._callback, None)  # session tap, at the head
                if tap:
                    break
            if not tap:
                raise PermissionError(t("macOS didn't let DisplayPad watch the mouse buttons (Input Monitoring)"))
            self._tap = tap
            self.state = "on" if option == 0 else "listen"
            src = macro._cf.CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = macro._cf.CFRunLoopGetCurrent()
            macro._cf.CFRunLoopAddSource(loop, src, macro._COMMON_MODES)
            macro._cg.CGEventTapEnable(tap, True)
            log.info("floating pad: watching the mouse%s", "" if option == 0 else
                     " (no Accessibility: the click also reaches the app under it)")
            while not stop.is_set():
                macro._cf.CFRunLoopRunInMode(macro._DEFAULT_MODE, 0.25, False)
        except Exception as e:
            log.warning("floating pad: %s", e)
            self.state = "error"
        finally:
            if self.state != "error":
                self.state = "off"
            if tap:
                macro._cg.CGEventTapEnable(tap, False)
                macro._cf.CFMachPortInvalidate(tap)
            if src:
                if loop:
                    macro._cf.CFRunLoopRemoveSource(loop, src, macro._COMMON_MODES)
                macro._cf.CFRelease(src)
            if tap:
                macro._cf.CFRelease(tap)
                if self._tap == tap:
                    self._tap = None

    def _on_event(self, proxy, kind, ev, refcon):
        try:
            if kind in macro._TAP_DISABLED:  # macOS turns a slow tap off; turn it back on
                if self._tap:
                    macro._cg.CGEventTapEnable(self._tap, True)
                return ev
            want = self._want
            if not want or kind not in (macro._OTHER_DOWN, macro._OTHER_UP) \
                    or macro._cg.CGEventGetIntegerValueField(ev, macro._SOURCE_PID) == os.getpid():  # our own macros
                return ev
            if keycapture.capture.state == "listening" and keycapture.capture._mouse \
                    and kind == macro._OTHER_DOWN:  # the person is recording a new trigger
                return ev
            button = macro._cg.CGEventGetIntegerValueField(ev, macro._BUTTON_NUMBER)
            if kind == macro._OTHER_UP:
                if button in self._held:
                    self._held.discard(button)
                    return None
                return ev
            if button == want[0] and macro._cg.CGEventGetFlags(ev) & _FLAG_MASK == want[1]:
                self._held.add(button)
                threading.Thread(target=self._fire, args=("mouse",), daemon=True).start()
                return None
            return ev
        except Exception:
            log.exception("floating pad: mouse")
            return ev


class Popup:
    """Talks to the DisplayPad app: tells it when to show the floating pad, and keeps it running."""

    def __init__(self, svc):
        self.svc = svc
        self.settings = None
        self.trigger = None
        self.tap = MouseTap(self.show)
        self.rev = int(time.time() * 1000) % 10**9  # a new one each start: the app reads the settings again
        self.app = {}                 # what the app last said ("hotkey": ok | off | taken | error...)
        self._cond = threading.Condition()
        self._event = None            # ("show", time)
        self._waiting = 0
        self._seen = 0.0              # the app's last request
        self._launched = -1e9
        self._missing = False         # `open` could not find the app
        self._started = False

    # -------------------------------------------------- the service
    def start(self):
        self._started = True
        self.configure(self.svc.cfg["popup"])
        threading.Thread(target=self._keep_app, name="popup-app", daemon=True).start()

    def configure(self, settings: dict):
        if settings == self.settings:
            return
        was_on = bool(self.settings and self.settings["enabled"])
        self.settings = dict(settings)
        self.trigger = parse(settings["trigger"])
        mouse = settings["enabled"] and self.trigger["kind"] == "mouse"
        if self._started:
            self.tap.set((self.trigger["button"], self.trigger["flags"]) if mouse else None)
        with self._cond:
            self.rev += 1
            self._cond.notify_all()
        log.info("floating pad: %s", settings["trigger"] if settings["enabled"] else "off")
        if self._started and settings["enabled"] and not was_on:  # just turned on: the app, now
            threading.Thread(target=self._ensure_app, args=(1.5,), daemon=True).start()

    def show(self, why="button"):
        """Brings up the floating pad (or puts it away, if it is up)."""
        if not (self.settings and self.settings["enabled"]) and why != "test":
            return
        with self._cond:
            if self._waiting or time.monotonic() - self._seen < EVENT_SECONDS:
                self._event = ("show", time.monotonic())
                self._cond.notify_all()
                return
        if self.running():  # running, but not asking: it will ask again soon
            with self._cond:
                self._event = ("show", time.monotonic())
            return
        self.launch("--popup")

    # -------------------------------------------------- the app
    def wait(self, rev: int, report: dict) -> dict:
        """The app's open request: returns when there is something to do, or after WAIT_SECONDS."""
        if report:
            self.app = report
        self._missing = False  # it is there
        deadline = time.monotonic() + WAIT_SECONDS
        with self._cond:
            self._waiting += 1
            self._seen = time.monotonic()
            try:
                while True:
                    event = self._event
                    if event and time.monotonic() - event[1] < EVENT_SECONDS:
                        self._event = None
                        return {"event": event[0], "popup": self.info()}
                    if rev != self.rev:
                        return {"event": "config", "popup": self.info()}
                    left = deadline - time.monotonic()
                    if left <= 0:
                        return {"event": "none", "popup": self.info()}
                    self._cond.wait(left)
            finally:
                self._waiting -= 1
                self._seen = time.monotonic()

    def info(self) -> dict:
        """What the app needs: the settings, and the key code of a keyboard shortcut."""
        s, tr = self.settings or {"enabled": False, "trigger": DEFAULT}, self.trigger or {}
        out = {"rev": self.rev, "enabled": s["enabled"], "trigger": s["trigger"], "kind": tr.get("kind", "mouse"),
               "language": self.svc.cfg["language"]}
        if tr.get("kind") == "key":
            out.update(code=tr["code"], carbon=tr["carbon"])
        return out

    def connected(self) -> bool:
        # the app asks again at once after each answer (within 5 seconds after an error)
        return bool(self._waiting) or time.monotonic() - self._seen < 8

    @staticmethod
    def running() -> bool:
        try:
            return subprocess.run(["pgrep", "-x", APP_PROCESS], capture_output=True, timeout=3).returncode == 0
        except Exception:
            return False

    def launch(self, arg="--background", soon=False):
        now = time.monotonic()
        # soon: just turned on (the caller saw no app running), so no wait
        if not soon and now - self._launched < (5 if arg == "--popup" else 600 if self._missing else LAUNCH_EVERY):
            return
        self._launched = now
        with self._cond:
            self._event = None  # the app shows it by itself when it starts with --popup
        from . import web  # circular
        cmd = ["open", "-g", "-b", APP_ID, "--args", arg, "--port", str(web.PORT), "--dir", self.svc.cfg["base_dir"]]

        def run():
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=15)
            except Exception as e:
                res = None
                log.warning("floating pad: could not start the DisplayPad app: %s", e)
            missing = res is not None and res.returncode != 0
            if missing and not self._missing:
                log.warning("floating pad: the DisplayPad app was not found; run install.sh again "
                            "(it needs the Xcode Command Line Tools: xcode-select --install)")
            self._missing = missing
            if not missing and res is not None:
                log.info("floating pad: started the DisplayPad app (%s)", arg)
        threading.Thread(target=run, daemon=True).start()

    def _keep_app(self):
        """Starts the app in the background (at login, after a crash) while the floating pad is on."""
        stop = self.svc._stop
        if stop.wait(4):  # a running app asks again within a second or two of a restart
            return
        while True:
            self._ensure_app()
            if stop.wait(30):
                return

    def _ensure_app(self, delay=0.0):
        """delay: the pad was just turned on. An app that quit when it was turned off may have
        asked a moment ago, so only whether it still runs counts."""
        try:
            if delay and self.svc._stop.wait(delay):
                return
            if not (self.settings and self.settings["enabled"]) or self.running():
                return
            if delay or not self.connected():
                self.launch("--background", soon=bool(delay))
        except Exception:
            log.exception("floating pad: app")

    def status(self) -> dict:
        s = self.settings or {"enabled": False, "trigger": DEFAULT}
        return {**s, "kind": (self.trigger or {}).get("kind", "mouse"), "app": self.connected(),
                "app_missing": self._missing, "hotkey": self.app.get("hotkey", ""), "mouse": self.tap.state}
