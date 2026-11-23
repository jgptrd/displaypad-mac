"""Background service: keeps the DisplayPad drawn and runs key actions.

- Reconnects by itself after unplug, sleep/wake or a device reset.
- Reloads config.json on save (no restart needed).
- Shows the pages linked to apps when those apps open or come to the front (appwatch).
- A watchdog exits the process if a USB write ever hangs; launchd restarts it.
- Animated keys: the pad keeps no animation of its own, so the main loop sends
  one frame at a time to whichever key is most overdue, and reads key presses
  between frames. The pad takes ~18 ms per key image, so ~50 frames per second
  are shared by all the animated keys of the page; when they ask for more,
  frames are skipped so every animation keeps its real speed.
- Live keys (live.py): the main loop sends a live key again when what it shows
  changes, one key per turn of the loop, sharing the pad with the animations.
- Moving backgrounds (render.py) are animations like any other. A key with a press
  effect plays it when pressed (about 33 frames a second, ahead of the animations)
  over whatever the key shows at that moment, in place of darkening it.
- Sound keys (sound.py): while a key's sound plays, a ring around the key shows how far it
  has got; the main loop sends the key again each time the ring moves on (up to 10 times a
  second), one key per turn, like live keys.
- The floating pad (popup.py): the same pages on the screen, brought up by a shortcut and shown
  by the DisplayPad app. Without the pad connected, the service still follows the pages linked
  to apps, so the floating pad opens on the right one.
"""

import bisect
import fcntl
import hashlib
import itertools
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Dict, List, Optional

from . import __version__, appwatch, i18n, keycapture, live, macos, macro, popup, sound, web
from .actions import NEEDS_POST_EVENTS, actions_of, run_actions, validate_action
from .driver import NUM_KEYS, DisplayPad, DisplayPadError, device_present
from .i18n import t
from .render import (DEFAULT_CORNER, EFFECT_STEP, EFFECTS, MAX_CORNER, RING_STEPS, crop_of, effect_of,
                     frame_durations, render_key, to_bgr, validate_background, validate_effect)

log = logging.getLogger(__name__)

APP_DIR = os.path.expanduser("~/Library/Application Support/DisplayPadMac")
DEFAULT_CONFIG = os.path.join(APP_DIR, "config.json")
WATCHDOG_SECONDS = 8
THEMES = ("system", "light", "dark")
SETTINGS = ("language", "theme", "brightness", "press_feedback", "corner_radius", "mcp", "popup")
# Inside a folder, key 1 is always this one: it goes back to the page or folder that holds it.
BACK_KEY = {"emoji": "⬅️", "color": "#2B2B33"}
BACK_LABEL = {"en": "Back", "es": "Volver"}


class ConfigError(Exception):
    pass


class ConfigConflict(ConfigError):
    """The file changed since the caller read it (another window or an AI assistant saved)."""


def _crop_ok(crop) -> bool:
    """[left, top, right, bottom] as fractions of the picture; it may reach past the
    edges (zoomed out), within reason."""
    c = crop_of({"crop": crop})
    return c is not None and all(-10 <= v <= 11 for v in c) and c[2] - c[0] <= 12 and c[3] - c[1] <= 12


def parse_config(cfg: dict, base_dir: str) -> dict:
    """Validate a raw config dict and return the normalised form the service uses."""
    if not isinstance(cfg, dict):
        raise ConfigError(t("the configuration must be a JSON object"))
    pages = cfg.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise ConfigError(t("at least one page is needed"))
    lang = cfg.get("language", "en")
    # Pages and the folders inside them, flattened: a folder is "<page>/<key>", one inside it
    # "<page>/<key>/<key>", and so on. Parents come before their folders.
    norm: Dict[str, List[Optional[dict]]] = {}

    def parse_keys(keys, pid: str, where: str, parent: Optional[str]):
        if not isinstance(keys, dict):
            raise ConfigError(t("page '{page}': keys must be an object like {{\"2\": {{...}}}}", page=where))
        slots: List[Optional[dict]] = [None] * NUM_KEYS
        if parent is not None:
            slots[0] = {**BACK_KEY, "label": BACK_LABEL.get(lang, "Back"), "_up": parent}
        norm[pid] = slots
        for k, spec in keys.items():
            if not str(k).isdigit() or not 1 <= int(k) <= NUM_KEYS:
                raise ConfigError(t("page '{page}': key '{key}' must be from 1 to 12", page=where, key=k))
            if spec is not None and not isinstance(spec, dict):
                raise ConfigError(t("page '{page}', key {key}: the key must be an object", page=where, key=k))
            if parent is not None and int(k) == 1:
                if spec:
                    raise ConfigError(t("page '{page}': key 1 of a folder is its back key; use keys 2 to 12", page=where))
                continue
            scale = (spec or {}).get("icon_scale", 100)
            if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 30 <= scale <= 200:
                raise ConfigError(t("page '{page}', key {key}: the icon size must be a number from 30 to 200", page=where, key=k))
            if not isinstance((spec or {}).get("hide_label", False), bool):
                raise ConfigError(t("page '{page}', key {key}: hide_label must be true or false", page=where, key=k))
            if (spec or {}).get("crop") is not None and not _crop_ok(spec["crop"]):
                raise ConfigError(t("page '{page}', key {key}: crop must be [left, top, right, bottom] as fractions "
                                    "of the picture, with right > left and bottom > top", page=where, key=k))
            for field, check in (("live", live.validate), ("background", validate_background),
                                 ("press_effect", validate_effect)):
                if (spec or {}).get(field) is not None:
                    err = check(spec[field])
                    if err:
                        raise ConfigError(t("page '{page}', key {key}: {error}", page=where, key=k, error=err))
            for a in actions_of(spec or {}):
                err = validate_action(a, pages)
                if err:
                    raise ConfigError(t("page '{page}', key {key}: {error}", page=where, key=k, error=err))
            if spec and "folder" in spec:
                folder = spec["folder"]
                if not isinstance(folder, dict):
                    raise ConfigError(t("page '{page}', key {key}: folder must be an object with its keys, "
                                        "like {{\"keys\": {{...}}}}", page=where, key=k))
                sub = f"{pid}/{int(k)}"
                spec = {**spec, "_folder": sub}
                parse_keys(folder.get("keys") or {}, sub, f"{where} › {spec.get('label') or spec.get('emoji') or k}", pid)
            slots[int(k) - 1] = spec or None

    for name, page in pages.items():
        if not str(name).strip():
            raise ConfigError(t("there is a page without a name"))
        if "/" in str(name):
            raise ConfigError(t("page '{page}': page names cannot contain “/”", page=name))
        if page is not None and not isinstance(page, dict):
            raise ConfigError(t("page '{page}': the page must be an object like {{\"keys\": {{...}}}}", page=name))
        parse_keys((page or {}).get("keys", {}), name, name, None)
    # pages linked to apps: shown while one of them is open, or while one is in front
    links = []
    for name, page in pages.items():
        apps = (page or {}).get("apps", [])
        if not isinstance(apps, list) or not all(isinstance(a, str) and a.strip() for a in apps):
            raise ConfigError(t("page '{page}': apps must be a list of app names", page=name))
        when = (page or {}).get("when", "open")
        if when not in appwatch.WHEN:
            raise ConfigError(t("page '{page}': when must be \"open\" or \"front\"", page=name))
        names = frozenset(map(appwatch.norm, apps))
        if names:
            links.append((name, names, when))
    start = cfg.get("start_page", next(iter(pages)))
    if start not in pages:
        raise ConfigError(t("the start page '{page}' does not exist", page=start))
    if lang not in i18n.LANGS:
        raise ConfigError(t("language must be one of: {values}", values=", ".join(i18n.LANGS)))
    theme = cfg.get("theme", "system")
    if theme not in THEMES:
        raise ConfigError(t("theme must be one of: {values}", values=", ".join(THEMES)))
    bright = cfg.get("brightness", 80)
    if isinstance(bright, bool) or not isinstance(bright, (int, float)):
        raise ConfigError(t("brightness must be a number from 0 to 100"))
    corner = cfg.get("corner_radius", DEFAULT_CORNER)
    if isinstance(corner, bool) or not isinstance(corner, (int, float)) or not 0 <= corner <= MAX_CORNER:
        raise ConfigError(t("corner_radius must be a number from 0 to {max}", max=MAX_CORNER))
    mcp = cfg.get("mcp", {})
    if not isinstance(mcp, dict) or not all(isinstance(v, bool) for v in mcp.values()):
        raise ConfigError(t("mcp must be an object with true/false values"))
    try:
        floating = popup.settings_of(cfg.get("popup"))
    except ValueError as e:
        raise ConfigError(t("floating pad: {error}", error=e))
    return {"pages": norm, "start_page": start, "links": links,
            "brightness": max(0, min(100, int(bright))),
            "press_feedback": bool(cfg.get("press_feedback", True)),
            "corner_radius": round(corner),
            "language": lang, "theme": theme,
            "mcp": {"enabled": mcp.get("enabled", False), "allow_run": mcp.get("allow_run", False)},
            "popup": floating, "base_dir": base_dir}


def load_config(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(t("{path}: invalid JSON at line {line}, column {col}: {msg}",
                            path=path, line=e.lineno, col=e.colno, msg=e.msg))
    return parse_config(cfg, os.path.dirname(os.path.abspath(path)))


class Service:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.pad = DisplayPad()
        self.config_error = ""
        try:
            self.cfg = load_config(config_path)
        except Exception as e:  # keep running so the configurator can fix it
            log.error("config error, starting with an empty page: %s", e)
            self.config_error = str(e)
            self.cfg = parse_config({"pages": {"home": {"keys": {}}}},
                                    os.path.dirname(os.path.abspath(config_path)))
        i18n.set_language(self.cfg["language"])
        self._mtime = os.path.getmtime(config_path)
        self.page = self.cfg["start_page"]
        self.history: List[str] = []
        self.brightness = self.cfg["brightness"]
        self._pending_page: Optional[str] = None
        self._pending_brightness: Optional[int] = None
        self._faces: Dict[tuple, bytes] = {}
        self._anims: Dict[int, dict] = {}        # key index -> timeline, frame shown, next due time
        self._anim_faces: Dict[tuple, bytes] = {}  # (key index, frame, pressed) -> BGR, current page only
        self._anim_stats = (0.0, 0.0)              # (frames per second sent, ms per frame) for the status
        self._anim_window: List[tuple] = []
        self._anim_sig: Dict[int, str] = {}         # live key index -> live picture its animation frames carry
        self.live = live.Engine(lambda: self.cfg["base_dir"])
        self.live.allow_commands(live.commands_in(self.cfg["pages"]))
        self._live_keys: Dict[int, str] = {}        # live key index on the current page -> picture sent
        self._live_faces: Dict[tuple, tuple] = {}   # (page, key index, pressed) -> (picture, BGR)
        self._live_due = 0.0
        self._pressed: set = set()
        self._dark: set = set()                     # pressed keys showing their darkened face
        self._fx: Dict[int, dict] = {}              # key index -> press effect playing: style, color, start, step
        self._fx_faces: Dict[tuple, bytes] = {}     # (key index, frame, step, live picture) -> BGR, current page only
        self._sound_keys: Dict[int, frozenset] = {}  # sound key index on the current page -> its sound files
        self._sound_sent: Dict[int, Optional[float]] = {}  # sound key index -> ring shown (None: not playing)
        self._sound_t: Dict[int, float] = {}        # sound key index -> when its ring was last sent
        self._sound_due = 0.0
        self._released: Dict[int, threading.Event] = {}  # pad key -> set when it is let go ("hold" shortcuts)
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._cfg_lock = threading.Lock()  # one read-modify-write of config.json at a time
        self.token = web.load_token(self.cfg["base_dir"])
        self.mcp_token = web.load_token(self.cfg["base_dir"], ".mcp-token")
        self.auto = appwatch.AutoPages()
        self.popup = popup.Popup(self)

    # -------------------------------------------------- called from actions
    def request_page(self, name: str):
        """A page name, a folder ("home/3"), "back" (the previous one) or "up" (out of a folder)."""
        if name in ("back", "up") or name in self.cfg["pages"]:
            self._pending_page = name

    def open_configurator(self):
        """In the DisplayPad app's own window; in the browser when the app can't be found."""
        def run():
            try:
                if subprocess.run(["open", "-b", popup.APP_ID], capture_output=True, timeout=15).returncode == 0:
                    return
            except Exception:
                pass
            subprocess.Popen(["open", web.configurator_url(self.token)])
        threading.Thread(target=run, daemon=True).start()

    # -------------------------------------------------- called from the configurator
    def status(self) -> dict:
        return {"connected": self.pad.connected, "page": self.page, "brightness": self.brightness,
                "input_monitoring": macos.input_monitoring_status(),
                "accessibility": macos.post_events_allowed(),
                "macros_playing": macro.playing(), "recording": macro.recorder.state,
                "python_app": os.path.join(sys.base_prefix, "Resources", "Python.app"),
                "config_error": self.config_error, "version": __version__,
                "config_rev": self.config_rev(), "config_path": self.config_path,
                "log_path": os.path.expanduser("~/Library/Logs/DisplayPadMac.log"),
                "language": self.cfg["language"], "mcp": self.cfg["mcp"],
                "animation": {"keys": len(self._anims), "fps": self._anim_stats[0],
                              "ms_per_frame": self._anim_stats[1]},
                "live": {"keys": len(self._live_keys), **self.live.status()},
                "sounds": {"keys": len(self._sound_keys), "playing": sound.playing_count()},
                "popup": self.popup.status()}

    def config_rev(self) -> str:
        """Short hash of config.json, so a window or an assistant can tell it changed under them."""
        try:
            with open(self.config_path, "rb") as f:
                return hashlib.sha1(f.read()).hexdigest()[:12]
        except OSError:
            return ""

    def read_config(self) -> dict:
        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def _write_config(self, raw: dict) -> str:
        parse_config(raw, self.cfg["base_dir"])  # raises ConfigError with a readable message
        if os.path.exists(self.config_path):
            shutil.copy2(self.config_path, self.config_path + ".previous")
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.config_path)
        self._reload.set()
        return self.config_rev()

    def save_config(self, raw: dict, expect_rev: str = "") -> str:
        """Replace the whole config (the configurator's Save). With expect_rev, refuse when
        the file changed since the caller loaded it. Returns the new revision."""
        with self._cfg_lock:
            if expect_rev and expect_rev != self.config_rev():
                raise ConfigConflict(t("the configuration was changed somewhere else (for example by an AI "
                                       "assistant); load it again before saving"))
            return self._write_config(raw)

    def update_config(self, change) -> str:
        """Read config.json, let change(raw) edit it in place, validate and save it."""
        with self._cfg_lock:
            raw = self.read_config()
            change(raw)
            return self._write_config(raw)

    def update_settings(self, patch: dict) -> str:
        """Save general settings at once, leaving pages and keys (and unsaved edits) alone."""
        for name in patch:
            if name not in SETTINGS:
                raise ConfigError(t("unknown setting '{name}'", name=name))
        for name in ("mcp", "popup"):
            if name in patch and not isinstance(patch[name], dict):
                raise ConfigError(t("{name} must be an object", name=name))

        def change(raw):
            for name, value in patch.items():
                if name in ("mcp", "popup"):
                    raw[name] = {**(raw.get(name) or {}), **value}
                else:
                    raw[name] = value
            if "popup" in patch:
                raw["popup"] = popup.settings_of(raw["popup"])  # the trigger written the usual way
        rev = self.update_config(change)
        if "language" in patch:
            i18n.set_language(patch["language"])
        if "mcp" in patch:  # at once, not after the main loop's reload: the next request may be an assistant's
            self.cfg["mcp"] = {**self.cfg["mcp"], **patch["mcp"]}
        if "popup" in patch:
            self.cfg["popup"] = popup.settings_of({**self.cfg["popup"], **patch["popup"]})
            self.popup.configure(self.cfg["popup"])
        return rev

    def change_brightness(self, value):
        if isinstance(value, str) and value[:1] in "+-":
            self._pending_brightness = max(0, min(100, self.brightness + int(value)))
        else:
            self._pending_brightness = max(0, min(100, int(value)))

    # -------------------------------------------------- drawing
    def _sound_at(self, idx: int) -> Optional[float]:
        """How far the sound of a key on the current page has got, in ring steps (None: not playing)."""
        files = self._sound_keys.get(idx)
        p = sound.progress(files) if files else None
        return None if p is None else round(p * RING_STEPS) / RING_STEPS

    def _face(self, page: str, idx: int, pressed: bool = False) -> bytes:
        spec = self.cfg["pages"][page][idx]
        lv = self.live.face(spec) if spec and "live" in spec else None
        if page == self.page and idx in self._sound_keys:
            pl = self._sound_sent[idx] = self._sound_at(idx)
            if pl is not None:  # its sound plays: drawn with the ring as it is now, and not kept
                a = self._anims.get(idx)
                if lv and not pressed and idx in self._live_keys:
                    self._live_keys[idx] = lv["sig"]
                return to_bgr(render_key(spec, self.cfg["base_dir"], pressed=pressed, frame=a["i"] if a else 0,
                                         corner=self.cfg["corner_radius"], live=lv, playing=pl))
        a = self._anims.get(idx) if page == self.page else None
        if a:  # animated: the frame currently shown
            sig = lv["sig"] if lv else ""
            if self._anim_sig.get(idx, "") != sig:  # the live text changed: older frames are no use
                self._anim_faces = {k: v for k, v in self._anim_faces.items() if k[0] != idx}
                self._anim_sig[idx] = sig
            key = (idx, a["i"], pressed)
            if key not in self._anim_faces:
                self._anim_faces[key] = to_bgr(render_key(spec, self.cfg["base_dir"], pressed=pressed, frame=a["i"],
                                                                   corner=self.cfg["corner_radius"], live=lv))
            if not pressed and idx in self._live_keys:
                self._live_keys[idx] = sig
            return self._anim_faces[key]
        if lv:  # live: drawn again when what it shows changes
            key = (page, idx, pressed)
            hit = self._live_faces.get(key)
            if not hit or hit[0] != lv["sig"]:
                hit = self._live_faces[key] = (lv["sig"], to_bgr(render_key(spec, self.cfg["base_dir"], pressed=pressed,
                                                                            corner=self.cfg["corner_radius"], live=lv)))
            if page == self.page and not pressed and idx in self._live_keys:
                self._live_keys[idx] = hit[0]
            return hit[1]
        key = (page, idx, pressed)
        if key not in self._faces:
            self._faces[key] = to_bgr(render_key(spec, self.cfg["base_dir"], pressed=pressed,
                                                     corner=self.cfg["corner_radius"]))
        return self._faces[key]

    def draw_page(self):
        t = time.monotonic()
        self._anims, self._anim_faces, self._anim_window, self._anim_stats = {}, {}, [], (0.0, 0.0)
        self._anim_sig, self._live_faces, self._fx, self._fx_faces, self._dark = {}, {}, {}, {}, set()
        specs = self.cfg["pages"][self.page]
        self._live_keys = {i: "" for i, spec in enumerate(specs) if spec and "live" in spec and not live.validate(spec["live"])}
        self.live.watch("pad", [specs[i]["live"] for i in self._live_keys])
        self._sound_keys, self._sound_sent = {}, {}
        for i, spec in enumerate(specs):
            files = frozenset(sound.resolve(a["file"], self.cfg["base_dir"]) for a in actions_of(spec)
                              if isinstance(a, dict) and a.get("type") == "sound" and a.get("file"))
            if files:
                self._sound_keys[i] = files
        for i, spec in enumerate(specs):
            durs = frame_durations(spec, self.cfg["base_dir"]) if spec and not live.is_meter(spec) else None
            if durs:
                ends = list(itertools.accumulate(durs))  # ms from the loop start at which each frame ends
                self._anims[i] = {"ends": ends, "total": ends[-1], "i": 0, "t0": 0.0, "due": 0.0, "sent": None}
        for i in range(NUM_KEYS):
            face = self._face(self.page, i)
            self.pad.upload(i, face)
            if i in self._anims:
                a = self._anims[i]
                a["t0"], a["sent"] = time.monotonic(), face
                a["due"] = a["t0"] + a["ends"][0] / 1000
        log.info("page '%s' drawn in %.2fs%s%s", self.page, time.monotonic() - t,
                 f", {len(self._anims)} animated key(s)" if self._anims else "",
                 f", {len(self._live_keys)} live key(s)" if self._live_keys else "")

    def _animate(self) -> float:
        """Send the frame that should be showing now on the most overdue animated key.
        Returns the seconds until another frame is due (0 right after sending one)."""
        hold = self._dark | self._fx.keys()
        due = [(a["due"], i) for i, a in self._anims.items() if i not in hold]
        if not due:
            return 0.04
        when, idx = min(due)
        now = time.monotonic()
        if when > now:
            return when - now
        a = self._anims[idx]
        pos = ((now - a["t0"]) * 1000 + 0.5) % a["total"]  # ms into the loop; frames in between are skipped
        i = min(bisect.bisect_right(a["ends"], pos), len(a["ends"]) - 1)
        end = now + (a["ends"][i] - pos) / 1000
        if i == a["i"]:
            a["due"] = end
            return 0.0
        a["i"] = i
        face = self._face(self.page, idx)
        if face == a["sent"]:  # nothing changed on this key, keep the USB time for the others
            a["due"] = end
            return 0.0
        t = time.monotonic()
        self.pad.upload(idx, face)
        done = time.monotonic()
        a["sent"], a["due"] = face, max(end, done)
        self._anim_window.append((done, done - t))
        if len(self._anim_window) >= 60:
            w = self._anim_window
            span = w[-1][0] - w[0][0]
            self._anim_stats = (round((len(w) - 1) / span, 1) if span > 0 else 0.0,
                                round(1000 * sum(d for _, d in w) / len(w), 1))
            self._anim_window = []
        return 0.0

    def _live_step(self) -> float:
        """Send one live key whose picture changed (animated ones change with their next
        frame). Returns the seconds until it is worth looking again."""
        if not self._live_keys:
            return 0.25
        now = time.monotonic()
        if now < self._live_due:
            return self._live_due - now
        hold = self._dark | self._fx.keys()
        specs = self.cfg["pages"][self.page]
        for idx, sent in self._live_keys.items():
            if idx in hold or idx in self._anims:
                continue
            lv = self.live.face(specs[idx])
            if lv and lv["sig"] != sent:
                self.pad.upload(idx, self._face(self.page, idx))
                return 0.0  # the others on the next turn, between key presses
        self._live_due = now + 0.1  # the clock's seconds stay on time
        return 0.1

    def _sound_step(self) -> float:
        """Send a sound key again when its ring has moved on, or its sound started or ended.
        Returns the seconds until it is worth looking again."""
        if not self._sound_keys:
            return 1.0
        now = time.monotonic()
        if now < self._sound_due:
            return self._sound_due - now
        hold = self._dark | self._fx.keys()
        for idx in self._sound_keys:
            at, sent = self._sound_at(idx), self._sound_sent.get(idx)
            if idx in hold or at == sent:
                continue
            if at is not None and sent is not None and now - self._sound_t.get(idx, 0.0) < 0.1:
                continue  # the ring moves on at most 10 times a second; starting and ending show at once
            self._show_now(idx)
            self._sound_t[idx] = time.monotonic()
            return 0.0  # the others on the next turn, between key presses
        self._sound_due = now + 0.05
        return 0.05

    def _show_now(self, idx: int):
        """Send a key as it is now (after it is let go, or its press effect ends); an
        animated key goes on from the frame due now."""
        a = self._anims.get(idx)
        if a:
            a["i"] = self._frame_now(a)
        face = self._face(self.page, idx)
        self.pad.upload(idx, face)
        if a:
            a["sent"], a["due"] = face, time.monotonic()

    @staticmethod
    def _frame_now(a: dict) -> int:
        pos = ((time.monotonic() - a["t0"]) * 1000 + 0.5) % a["total"]
        return min(bisect.bisect_right(a["ends"], pos), len(a["ends"]) - 1)

    def _fx_step(self, only: Optional[int] = None) -> float:
        """Send the next frame of the press effect most overdue (or of key `only`), or put
        the key back when its effect is over. Returns the seconds until another is due."""
        if not self._fx:
            return 1.0
        now = time.monotonic()
        if only is None:
            when, idx = min((f["due"], i) for i, f in self._fx.items())
            if when > now:
                return when - now
        else:
            idx = only
        f = self._fx[idx]
        total = EFFECTS[f["style"]]
        at = (now - f["t0"]) * 1000
        if at >= total:
            del self._fx[idx]
            self._show_now(idx)
            return 0.0
        step = int(at // EFFECT_STEP)
        spec = self.cfg["pages"][self.page][idx]
        lv = self.live.face(spec) if spec and "live" in spec else None
        a = self._anims.get(idx)
        frame = self._frame_now(a) if a else 0  # the key goes on moving under the effect
        pl = self._sound_at(idx)
        if idx in self._sound_keys:
            self._sound_sent[idx] = pl
        key = (idx, frame, step, lv["sig"] if lv else "", pl)
        face = self._fx_faces.get(key)
        if face is None:
            if len(self._fx_faces) > 600:
                self._fx_faces.clear()
            face = self._fx_faces[key] = to_bgr(render_key(
                spec, self.cfg["base_dir"], frame=frame, corner=self.cfg["corner_radius"], live=lv,
                effect=(f["style"], f["color"], step * EFFECT_STEP / total), playing=pl))
        self.pad.upload(idx, face)
        f["due"] = f["t0"] + (step + 1) * EFFECT_STEP / 1000
        return 0.0

    # -------------------------------------------------- main loop
    def _let_go(self):
        """The pad is gone or the service stops: let go of keys held by "hold" shortcuts."""
        self.live.watch("pad", [])  # nothing to show the readings on
        for ev in self._released.values():
            ev.set()
        self._released.clear()
        self._pressed, self._dark = set(), set()
        macro.stop_all()
        macos.release_all()

    def _connect(self):
        self.pad.open()
        self.pad.set_brightness(self.brightness)
        self._pressed, self._dark, self._fx = set(), set(), {}
        self._let_go()
        self.draw_page()

    def _check_config(self):
        try:
            mtime = os.path.getmtime(self.config_path)
        except OSError:
            return
        if mtime == self._mtime:
            return
        self._mtime = mtime
        try:
            cfg = load_config(self.config_path)
        except Exception as e:
            self.config_error = str(e)
            log.error("config not reloaded: %s", e)
            return
        self.config_error = ""
        self.cfg, self._faces = cfg, {}
        self.live.allow_commands(live.commands_in(cfg["pages"]))
        macro.keep_only(a for page in cfg["pages"].values() for spec in page if spec for a in actions_of(spec))
        i18n.set_language(cfg["language"])
        self.popup.configure(cfg["popup"])
        if self.page not in cfg["pages"]:
            self.page, self.history = cfg["start_page"], []
        if cfg["brightness"] != self.brightness:
            self._pending_brightness = cfg["brightness"]
        log.info("config reloaded")
        if self.pad.connected:
            self.draw_page()

    def _on_keys(self, keys: set):
        for k in sorted(keys - self._pressed):
            if macro.recorder.active():  # any pad key ends a macro recording, and does nothing else
                macro.recorder.stop("pad")
                log.info("macro recording stopped from the pad (key %d)", k + 1)
                continue
            spec = self.cfg["pages"][self.page][k]
            log.info("key %d pressed on '%s'", k + 1, self.page)
            fx = effect_of(spec)
            if fx:  # plays over the key, from the first frame now
                self._dark.discard(k)
                self._fx[k] = {"style": fx[0], "color": fx[1], "t0": time.monotonic(), "due": 0.0}
                self._fx_step(k)
            elif spec and self.cfg["press_feedback"]:
                self._dark.add(k)
                self.pad.upload(k, self._face(self.page, k, pressed=True))
            if spec:
                released = self._released[k] = threading.Event()
                threading.Thread(target=run_actions, args=(spec, self, released), daemon=True).start()
                if spec.get("_up"):  # the back key of a folder
                    self.request_page("up")
                elif spec.get("_folder"):  # opens after its own actions start, when every key is up
                    self.request_page(spec["_folder"])
        for k in sorted(self._pressed - keys):
            released = self._released.pop(k, None)
            if released:
                released.set()
            if k in self._dark:  # a press effect puts the key back by itself when it ends
                self._dark.discard(k)
                if self._pending_page is None:
                    self._show_now(k)
        self._pressed = keys

    def _apply_pending(self, draw: bool = True):
        """draw=False: the pad is not connected; follow the page (for the floating pad) and draw
        it when the pad comes back."""
        if draw and self._pending_brightness is not None:
            self.brightness, self._pending_brightness = self._pending_brightness, None
            self.pad.set_brightness(self.brightness)
            log.info("brightness %d%%", self.brightness)
        if self._pending_page is not None and not self._pressed:
            target, self._pending_page = self._pending_page, None
            if target == "up":  # out of a folder, to the page or folder that holds it
                target = self.page.rpartition("/")[0] or self.cfg["start_page"]
                if self.history and self.history[-1] == target:
                    self.history.pop()
            elif target == "back":
                target = self.history.pop() if self.history else self.cfg["start_page"]
            elif target != self.page:
                self.history = (self.history + [self.page])[-20:]
            if target not in self.cfg["pages"]:  # page deleted in the configurator
                target, self.history = self.cfg["start_page"], []
            self.page = target
            if draw:
                self.draw_page()

    def _watch_apps(self):
        """Shows the pages linked to apps (see appwatch); its own thread, so a slow look at
        the windows never delays the pad."""
        apps = appwatch.Apps()
        cfg, running, next_list = None, set(), 0.0
        while not self._stop.wait(appwatch.FRONT_SECONDS):
            try:
                if self.cfg is not cfg:
                    cfg = self.cfg
                    if cfg["links"]:
                        self.auto.configure(cfg["links"])
                    else:
                        self.auto = appwatch.AutoPages()  # start afresh when links come back
                if not cfg["links"]:
                    continue
                now = time.monotonic()
                if now >= next_list:
                    running, next_list = apps.running(), now + appwatch.RUNNING_SECONDS
                target = self.auto.update(running, apps.front(), self.page)
                if target:
                    pages = self.cfg["pages"]
                    if target not in pages:  # a folder or page that has gone since
                        top = target.split("/")[0]
                        target = top if top in pages else self.cfg["start_page"]
                    log.info("%s -> showing '%s'", self.auto.reason, target)
                    self._pending_page = target
            except Exception:
                log.exception("watching apps")
                self._stop.wait(5)

    def _watchdog(self):
        while not self._stop.wait(1):
            since = self.pad.busy_since
            if since and time.monotonic() - since > WATCHDOG_SECONDS:
                log.critical("USB write hung for %ss, exiting so launchd restarts the service", WATCHDOG_SECONDS)
                os._exit(3)

    def run(self):
        threading.Thread(target=self._watchdog, daemon=True).start()
        threading.Thread(target=self._watch_apps, name="appwatch", daemon=True).start()
        self.live.start()
        web.start(self, self.token)
        self.popup.start()
        last_cfg_check = 0.0
        waiting_logged = False
        while not self._stop.is_set():
            if self._reload.is_set() or time.monotonic() - last_cfg_check > 1:
                self._reload.clear()
                last_cfg_check = time.monotonic()
                self._check_config()
            if not self.pad.connected:
                self._apply_pending(draw=False)
                if not device_present():
                    if not waiting_logged:
                        log.info("waiting for the DisplayPad to be connected...")
                        waiting_logged = True
                    self._stop.wait(1.5)
                    continue
                try:
                    self._connect()
                    waiting_logged = False
                    log.info("DisplayPad ready")
                except PermissionError as e:
                    log.error("%s", e)
                    self.pad.close()
                    self._stop.wait(10)
                except Exception as e:
                    log.warning("connect failed: %s", e)
                    self.pad.close()
                    self._stop.wait(2)
                continue
            try:
                self._apply_pending()
                wait = min(self._fx_step(), self._animate(), self._live_step(), self._sound_step())
                keys = self.pad.read_keys(max(1, min(40, int(wait * 1000))))
                if keys is not None:
                    self._on_keys(keys)
            except (DisplayPadError, OSError, ValueError) as e:
                log.warning("device lost: %s", e)
                self.pad.close()
                self._let_go()
            except Exception as e:  # pyusb errors and anything unexpected
                log.warning("device error: %s", e)
                self.pad.close()
                self._let_go()
        self.pad.close()
        self._let_go()
        self.live.stop()
        sound.stop_all()  # afplay runs on its own: stop what this service started

    def stop(self, *_):
        keycapture.capture.cancel()  # give the keyboard back first
        self.popup.tap.set(None)
        self._stop.set()


def check_permissions(cfg: dict):
    if os.environ.get("DISPLAYPAD_NO_PROMPT"):
        return
    status = macos.input_monitoring_status()
    if status != "granted":
        log.warning("Input Monitoring is %s; asking macOS for it", status)
        macos.request_input_monitoring()
    uses_events = any(a.get("type") in NEEDS_POST_EVENTS
                      for page in cfg["pages"].values() for spec in page if spec
                      for a in actions_of(spec))
    if uses_events and not macos.post_events_allowed():
        log.warning("Accessibility (keyboard control) not granted; shortcuts/text/media keys "
                    "will not work until it is allowed in System Settings > Privacy & Security")
        macos.request_post_events()


def single_instance():
    fh = open(os.path.join(tempfile.gettempdir(), f"displaypadmac-{os.getuid()}.lock"), "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another DisplayPadMac instance is already running "
                         "(stop it with: launchctl bootout gui/$(id -u)/com.displaypadmac.agent)")
    return fh


def main(config_path: str):
    lock = single_instance()  # noqa: F841 (held for the life of the process)
    svc = Service(config_path)
    signal.signal(signal.SIGTERM, svc.stop)
    signal.signal(signal.SIGINT, svc.stop)
    check_permissions(svc.cfg)
    log.info("DisplayPadMac running with %s", config_path)
    svc.run()
    log.info("stopped")
