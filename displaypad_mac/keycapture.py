"""Records one keyboard shortcut system-wide, for the configurator's Record button.

A browser page only sees the keys macOS and the browser leave it: ⌘⇧4, ⌘Space, ⌘Tab, ⌘Q,
⌘W or fn do their own thing and the page gets half a shortcut, or nothing. While this
listens, an active event tap holds every key press back from macOS and all apps, and
records it here instead (with left and right modifiers apart, like the page did).

It lets go of the keyboard:
  - when the shortcut is complete and its keys are up again (at most DRAIN_SECONDS later),
  - when the configurator stops asking for news (tab closed, window left): HEARTBEAT_SECONDS,
  - after CAPTURE_SECONDS without a shortcut, or on cancel,
and macOS frees it anyway if the service quits. Caps lock and keys that were already down
when it started pass through, so nothing is left stuck.

Rules, the same as the page's: a normal key ends it with the modifiers held at that moment
("cmd+shift+4", "f13"); modifiers pressed and let go with no other key are recorded on
their own ("rcmd", "ctrl+rshift").

With mouse=True (the floating pad's trigger) a click of the middle or an extra mouse button
also ends it, with the modifiers held: "cmd+middle_click", "alt+mouse4". The click is held
back from the app under the mouse.
"""

import ctypes
import ctypes.util
import logging
import os
import threading
import time

from . import macos, macro
from .i18n import t

log = logging.getLogger(__name__)

_cg, _cf = macro._cg, macro._cf

CAPTURE_SECONDS = 30
HEARTBEAT_SECONDS = 2.0
DRAIN_SECONDS = 3.0

_KEY_DOWN, _KEY_UP, _FLAGS = macro._KEY_DOWN, macro._KEY_UP, macro._FLAGS
_TAP_DISABLED = macro._TAP_DISABLED
_AUTOREPEAT, _KEYCODE, _SOURCE_PID = macro._AUTOREPEAT, macro._KEYCODE, macro._SOURCE_PID
_OTHER_DOWN, _OTHER_UP, _BUTTON_NUMBER = macro._OTHER_DOWN, macro._OTHER_UP, macro._BUTTON_NUMBER
_MOUSE_NAMES = {2: "middle_click", 3: "mouse4", 4: "mouse5"}
_SIDE_BITS = macro._SIDE_BITS

MOD_ORDER = ("fn", "ctrl", "rctrl", "alt", "ralt", "shift", "rshift", "cmd", "rcmd")  # ⌃⌥⇧⌘
_MOD_CODES = {code: name for name, (code, _, _) in macos.MOD_KEYS.items()}
# the names the configurator uses (and parse_shortcut accepts)
_NAMES = {}
for _name, _code in macos.KEYCODES.items():
    _NAMES.setdefault(_code, _name)
_NAMES.update({36: "return", 51: "delete", 53: "esc"})

try:
    _carbon = ctypes.CDLL(ctypes.util.find_library("Carbon"))
    _carbon.IsSecureEventInputEnabled.restype = ctypes.c_bool
except (OSError, AttributeError):
    _carbon = None


def secure_input() -> bool:
    """True while some app has Secure Keyboard Entry on (a password field, Terminal's
    option...): then no tap sees the keyboard, and only the app in front gets the keys."""
    try:
        return bool(_carbon and _carbon.IsSecureEventInputEnabled())
    except Exception:
        return False


def _sort(mods):
    return sorted(set(mods), key=MOD_ORDER.index)


class Capture:
    """States: idle -> listening -> done (the combo) | cancelled | error."""

    def __init__(self):
        self._lock = threading.Lock()
        self._callback = macro._TAP_CALLBACK(self._on_event)
        self._thread = None
        self._tap = None
        self._stop = threading.Event()
        self.state, self.combo, self.live, self.error, self.ended_by = "idle", "", "", "", ""
        self._seen = 0.0
        self._mouse = False
        self._buttons = set()  # mouse buttons whose release is held back too

    # -------------------------------------------------- control (web threads)
    def start(self, mouse: bool = False) -> dict:
        with self._lock:
            self._end_thread()
            self._mouse, self._buttons = mouse, set()
            self._stop = threading.Event()
            self.state, self.combo, self.live, self.error, self.ended_by = "starting", "", "", "", ""
            self._held, self._down, self._mods = set(), set(), []
            self._done_at = 0.0
            self._seen = time.monotonic()
            ready = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stop, ready), name="keycapture", daemon=True)
            self._thread.start()
        ready.wait(2.0)
        return self.status(touch=False)

    def cancel(self, by="cancel") -> dict:
        """Stops listening. A shortcut already recorded keeps the keyboard until its keys are
        up (DRAIN_SECONDS at most), so a held key cannot auto-repeat into macOS."""
        with self._lock:
            if self.state in ("starting", "listening"):
                self.ended_by = by
                self.state = "cancelled"
                self._stop.set()
        return self.status(touch=False)

    def active(self) -> bool:
        return self.state in ("starting", "listening")

    def status(self, touch=True) -> dict:
        if touch:
            self._seen = time.monotonic()
        return {"state": self.state, "combo": self.combo, "live": self.live, "error": self.error,
                "ended_by": self.ended_by, "secure_input": secure_input()}

    def _end_thread(self):
        th = self._thread
        if th and th.is_alive():
            self._stop.set()
            th.join(1.0)

    # -------------------------------------------------- the tap (its own thread)
    def _run(self, stop, ready):
        tap = src = loop = None
        try:
            mask = (1 << _KEY_DOWN) | (1 << _KEY_UP) | (1 << _FLAGS)
            if self._mouse:
                mask |= (1 << _OTHER_DOWN) | (1 << _OTHER_UP)
            # active tap (options 0: it may drop events) at the head, where HID events enter
            # the window server, before macOS looks for its own shortcuts; the session is the
            # fallback. Both need the Accessibility permission.
            for where in (0, 1):
                tap = _cg.CGEventTapCreate(where, 0, 0, mask, self._callback, None)
                if tap:
                    break
            if not tap:
                raise PermissionError(t("the Accessibility permission is needed to record shortcuts from the whole Mac"))
            self._tap = tap
            src = _cf.CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = _cf.CFRunLoopGetCurrent()
            _cf.CFRunLoopAddSource(loop, src, macro._COMMON_MODES)
            _cg.CGEventTapEnable(tap, True)
            started = time.monotonic()
            if self.state == "starting":
                self.state = "listening"
            ready.set()
            log.info("shortcut capture started (%s tap)", "HID" if where == 0 else "session")
            while not stop.is_set():
                _cf.CFRunLoopRunInMode(macro._DEFAULT_MODE, 0.05, False)
                now = time.monotonic()
                if self.state == "listening":
                    if now - self._seen > HEARTBEAT_SECONDS:
                        self.ended_by, self.state = "gone", "cancelled"
                    elif now - started > CAPTURE_SECONDS:
                        self.ended_by, self.state = "timeout", "cancelled"
                if self.state == "done" and (not (self._held or self._buttons) or now - self._done_at > DRAIN_SECONDS):
                    break
                if self.state not in ("listening", "done"):
                    break
            log.info("shortcut capture ended: %s", self.combo or self.ended_by or self.state)
        except Exception as e:
            log.warning("shortcut capture failed: %s", e)
            self.error, self.state = str(e), "error"
        finally:
            ready.set()
            if tap:
                _cg.CGEventTapEnable(tap, False)
                _cf.CFMachPortInvalidate(tap)
            if src:
                if loop:
                    _cf.CFRunLoopRemoveSource(loop, src, macro._COMMON_MODES)
                _cf.CFRelease(src)
            if tap:
                _cf.CFRelease(tap)
                if self._tap == tap:
                    self._tap = None

    def _on_event(self, proxy, kind, ev, refcon):
        try:
            if kind in _TAP_DISABLED:  # macOS turns a slow tap off; turn it back on
                if self._tap:
                    _cg.CGEventTapEnable(self._tap, True)
                return ev
            if self.state not in ("listening", "done") or kind not in (_KEY_DOWN, _KEY_UP, _FLAGS, _OTHER_DOWN, _OTHER_UP) \
                    or _cg.CGEventGetIntegerValueField(ev, _SOURCE_PID) == os.getpid():  # our own shortcuts and macros
                return ev
            if kind in (_OTHER_DOWN, _OTHER_UP):
                return ev if self._click(kind, ev) else None
            return ev if self._key(kind, ev) else None
        except Exception:
            log.exception("shortcut capture")
            return ev

    def _key(self, kind, ev) -> bool:
        """Handles one key event; True lets it through to macOS and the apps."""
        code = _cg.CGEventGetIntegerValueField(ev, _KEYCODE)
        flags = _cg.CGEventGetFlags(ev)
        mod = None
        if kind == _FLAGS:
            mod = _MOD_CODES.get(code)
            if not mod:
                return True  # caps lock: it is a switch, let macOS keep track of it
            _, mask, side = macos.MOD_KEYS[mod]
            down = bool(flags & side) if side and flags & _SIDE_BITS else \
                (bool(flags & mask) if mod == "fn" else code not in self._held)
        else:
            down = kind == _KEY_DOWN
        if not down:
            if code not in self._held:
                return True  # a key that was down before we started: macOS must see it go up
            self._held.discard(code)
            if mod and self.state == "listening":
                self._down.discard(mod)
                if not self._down and self._mods:  # modifiers on their own
                    self._finish("+".join(_sort(self._mods)))
            return False
        if self.state == "done":
            return False  # still letting go of the shortcut: auto-repeats and extra keys stay out
        if kind == _KEY_DOWN and _cg.CGEventGetIntegerValueField(ev, _AUTOREPEAT):
            return False
        self._held.add(code)
        if mod:
            if mod not in self._down:
                self._down.add(mod)
                self._mods.append(mod)
            self.live = "+".join(_sort(self._down))
            return False
        name = _NAMES.get(code)
        if not name:
            return False  # a key the shortcuts cannot name: keep listening
        # modifiers held now: the side the event says, or the one we saw go down
        held = []
        for m in ("ctrl", "alt", "shift", "cmd"):
            _, mask, _ = macos.MOD_KEYS[m]
            if not flags & mask:
                continue
            sides = [s for s in (m, "r" + m) if flags & macos.MOD_KEYS[s][2]]
            held += sides or [s for s in (m, "r" + m) if s in self._down] or [m]
        if "fn" in self._down:
            held.append("fn")
        self._finish("+".join(_sort(held) + [name]))
        return False

    def _click(self, kind, ev) -> bool:
        """A middle or extra mouse button (mouse=True only); True lets it through."""
        button = _cg.CGEventGetIntegerValueField(ev, _BUTTON_NUMBER)
        if kind == _OTHER_UP:
            if button in self._buttons:
                self._buttons.discard(button)
                return False
            return True
        name = _MOUSE_NAMES.get(button)
        if not self._mouse or not name or self.state != "listening":
            return True
        self._buttons.add(button)
        flags = _cg.CGEventGetFlags(ev)
        mods = [m for m in ("ctrl", "alt", "shift", "cmd") if flags & macos.MOD_KEYS[m][1]]
        self._finish("+".join(mods + [name]))
        return False

    def _finish(self, combo):
        self.combo, self.live = combo, combo
        self._done_at = time.monotonic()
        self.state = "done"


capture = Capture()
