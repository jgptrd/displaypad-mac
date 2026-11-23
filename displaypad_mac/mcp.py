"""MCP server: lets AI assistants (Claude, Cursor, VS Code, ...) read and change the
DisplayPad setup through the Model Context Protocol, so they can help the user
build pages, keys and automations.

Transport: "Streamable HTTP" at http://127.0.0.1:8765/mcp (web.py checks the
access key and routes each JSON-RPC message here). Answers are plain JSON; the
server never starts messages of its own. Apps that can only launch a local
command use `python -m displaypad_mac mcp` (stdio_bridge below), which forwards
every message to that address with the key from .mcp-token.

Every change goes through Service.update_config: it is validated like a save in
the configurator, written atomically (the previous file stays as
config.json.previous) and shows on the pad within a second. An open configurator
window notices and reloads.
"""

import base64
import io
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

from . import __version__, actions, appwatch, browsers, daemon, live, obs, presets, render, sound, web  # daemon/web: circular, used at call time only

log = logging.getLogger(__name__)

PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first
MAX_UPLOAD = 12 * 1024 * 1024

INSTRUCTIONS = """\
These tools set up the user's Mountain DisplayPad on this Mac: 12 keys with a small screen each \
(2 rows of 6; keys 1-6 top row, 7-12 bottom row), grouped in pages; a key can also be a folder \
that holds more keys (folders can hold folders). Each key has a look (emoji, \
picture or animation, label, colors), can show something live (the time, CPU/GPU/RAM use, \
battery, volume, what is playing, OBS, a command's output) and has a list of actions run when it \
is pressed (open apps or \
websites, keyboard shortcuts, typed text, media keys, macros of keyboard and mouse steps, \
sounds, shell commands, AppleScript, page switches, brightness).

Call get_reference once for every key field and action type. Look before you change anything \
(list_pages, get_config) and ask before replacing keys the user already uses. Changes are saved at \
once and appear on the pad within a second; check the look with preview_page and switch the pad \
with show_page. test_actions runs actions right away and only works if the user allowed it in \
DisplayPad Settings > AI assistants."""

REFERENCE = """\
DisplayPad for Mac: configuration reference

THE DEVICE
- 12 keys, each a 102x102 pixel screen, in 2 rows of 6: keys 1-6 are the top row (left to right), 7-12 the bottom row.
- The configuration has one or more pages; the pad shows one at a time. start_page is shown when the service starts. The "page" action switches pages; page "back" returns to the previous one.
- Folders: any key can be a folder that opens when pressed. Inside a folder, key 1 is always a fixed Back key (out to the page or folder that holds it), so a folder has keys 2-12; folders can be inside folders. Tools address a folder as "<page>/<key>": "home/3" is the folder on key 3 of page "home", "home/3/5" the folder on key 5 inside it. Use that wherever a tool takes a page (get_key, set_key, clear_key, show_page, preview_page); list_pages lists every folder.
- Ready-made pages: list_app_presets lists pages with the most-used shortcuts of popular apps; add_app_preset creates one (linked to the app while it is in front; the OBS one while OBS is open) or adds its keys to an existing page.
- Pages can open by themselves, like profiles: link_page_to_apps links a page to apps (names as list_apps gives them). With when "open" the pad shows the page when one of the apps opens and goes back when the last one quits; with "front" it shows it whenever one of them is in front and goes back when you switch to another app. Going back only happens if the pad still shows that page.

KEY FIELDS (all optional; a key with nothing is simply left out)
- emoji: drawn as the icon, e.g. "📧".
- image: a picture in the configuration folder, e.g. "icons/icono-1a2b3c4d.png". Add PNG/JPG pictures, animated GIF/WebP or Lottie animations with upload_image and use the path it returns. Animations play on the pad (about 50 frames per second in total for all animated keys of a page).
- label: text at the bottom of the key, under the icon (about 8-10 characters fit per line; longer text shrinks and wraps). A key with only a label shows it large in the middle.
- hide_label: true keeps the label in the configuration without drawing it.
- color: background "#RRGGBB" (default "#1C1C24"). text_color: label color (default "#FFFFFF").
- background: a gradient in place of the plain color: {"style": "gradient", "colors": ["#FF5F6D", "#FFC371"]}. Styles: gradient (still), animated (the colors keep flowing along the angle), waves (wavy bands of the colors that roll by), solid (the plain color). colors: 2 or 3 "#RRGGBB". angle: degrees, as in CSS (0 towards the top, 90 towards the right; default 135, waves 180). speed: 0.25-4 for animated and waves (default 1; 0.5 slow, 2 fast). Moving backgrounds play on the pad like animations (about 15 frames a second each) and share its speed with them. Keep "color" too: meters and amber/red alerts use it. Nice pairs: sunset #FF5F6D/#FFC371, ocean #2193B0/#6DD5ED, purple #7F00FF/#E100FF, aurora #00C9A7/#845EC2, fire #F12711/#F5AF19, mint #11998E/#38EF7D, candy #FC5C7D/#6A82FB, night #232526/#414345. Example: {"emoji": "🎵", "label": "Music", "background": {"style": "waves", "colors": ["#FC5C7D", "#6A82FB"]}}.
- press_effect: an animation played over the key on the pad each time it is pressed, in place of darkening it: {"style": "ripple"}. Styles: ripple (a ring spreading from the middle), flash, glow (the edge lights up), sparkle (little stars flying out), shine (a band of light sweeping across), bounce (the key pushed in and springing back). color: "#RRGGBB" of the effect (default "#FFFFFF"; bounce has none). Keys that open a page or folder switch at once, so their effect is cut short.
- fill: images only. true (default) makes a picture cover the whole key when no label is drawn; false keeps a margin.
- icon_scale: 30-200, size of the emoji or picture in percent (default 100; over 100 zooms in).
- crop: [left, top, right, bottom] for pictures, as fractions of the picture (0-1), e.g. [0.25, 0, 0.75, 1] for the middle square of a 2:1 picture. Keys are square, so make the cropped area square in pixels or the picture is centred inside it (never stretched). Without crop the middle of the picture covers the key, or, on a key with visible text or fill false, the whole picture is shown smaller. Values past 0-1 zoom out: that part shows the key color (for a 2:1 picture, [0, -0.5, 1, 1.5] shows it whole). upload_image tells the picture's size. Setting a new image without crop drops the old crop.
- actions: list of actions run in order when the key is pressed. ("action": {...} with a single action is also accepted.)
- live: {"source": "cpu"} makes the key show something that keeps changing; the pad redraws it by itself. Sources: clock (time and date), cpu, gpu, ram, battery, volume (output), mic (input level), music (what Music or Spotify plays; only an app already open is asked, and macOS asks the user once to allow it), obs (streaming, recording, scene; uses the connection in Settings > OBS), command (with "command": a zsh command, and "every": seconds between runs, 2-3600, default 10; shows the first line it prints). The label is the text shown, with values in braces: clock {time} {time12} {ampm} {seconds} {weekday} {day} {month} {year} {date}; cpu/gpu {value}; ram {value} {used} {total} (GB); battery {value} {state}; volume/mic {value} {state}; music {title} {artist} {app} {state}; obs {status} {scene} {stream_time} {record_time}; command {output} {value}. Without a label: "{time}", "CPU {value}%", "{title}", "{status}"... An emoji or picture stays above the text. "style": "meter" (cpu, gpu, ram, battery, volume, mic, or a command that prints a number 0-100) draws a gauge instead: the label as its title, the number, the last minute as a line and a bar that turns amber at 70% and red at 90% (ram: by memory pressure; battery: when low). A text key turns amber or red when the reading needs attention (OBS live or recording, mic at 0, sound muted, CPU/GPU high, battery low, a failing command); "alert": false keeps its color. Readings are only taken while the key is on the pad or open in the configurator. A command source can only be set by you when the user turned on "Allow running actions" in Settings > AI assistants (otherwise ask them to add it in the configurator). Examples: {"label": "{time}", "live": {"source": "clock"}}; {"label": "CPU", "color": "#1A1A19", "live": {"source": "cpu", "style": "meter"}}.
- folder: {"keys": {"2": spec, "3": spec, ...}} makes the key a folder (keys 2-12; key 1 is the Back key). Make an empty one with {"folder": {"keys": {}}} plus a look (e.g. "emoji": "📁", "label": "Work"), then fill it with set_key on page "<page>/<key>". A folder key may have actions too: they run, then the folder opens. To change a folder key's look use set_key with merge true: replacing the whole key would drop the folder, so set_key refuses that while the folder has keys.

ACTIONS
- {"type": "open", "target": "Safari"}: an app name (see list_apps), a URL ("https://...", "mailto:...", "zoommtg://...") or a file/folder path ("~/Documents").
  For http(s) addresses, optional: "browser": a browser's app name from list_browsers (default: the Mac's default browser); "new": "tab" (default) or "window"; "reuse_tab": true goes to the tab that already shows the address instead of opening another (a tab matches when its address starts with the target's, ignoring http/https, "www." and "#...", so "https://web.whatsapp.com" finds any WhatsApp tab). Use reuse_tab for web apps people keep open (WhatsApp, Gmail, Slack, Teams). Safari and the Chromium browsers (Chrome, Edge, Brave, Vivaldi) can do new windows and reuse_tab; other browsers open the address as a link. The first time, macOS asks the user to let DisplayPad control the browser. Example: {"type": "open", "target": "https://web.whatsapp.com", "browser": "Google Chrome", "reuse_tab": true}.
- {"type": "shortcut", "keys": "cmd+shift+4"}: modifiers and one key, a single key ("f13") or modifiers alone ("rcmd", "ctrl+rshift"). Modifiers: cmd, shift, ctrl, alt (or option), fn are the left keys; rcmd, rshift, rctrl, ralt are the right ones, for apps that listen to one side. Keys: a-z, 0-9, f1-f20, return, tab, space, delete, forwarddelete, esc, up, down, left, right, home, end, pageup, pagedown, help, section, eisu, kana, keypad kp0-kp9, kpdecimal, kpplus, kpminus, kpmultiply, kpdivide, kpequals, kpenter, kpclear, and - = [ ] \\ ; ' , . / `. Add "hold": true to keep the keys down while the pad key is held and let them go when it is released (push-to-talk and other apps that listen for a held key; at most 10 minutes); without it they are pressed and let go at once. Goes to the app in front.
- {"type": "text", "text": "Best regards,\\n"}: typed where the cursor is (any Unicode; \\n presses Return).
- {"type": "media", "key": "play_pause"}: play_pause, next, previous, volume_up, volume_down, mute, brightness_up, brightness_down.
- {"type": "shell", "command": "open -a Safari https://apple.com"}: runs with zsh -lc in the background; nobody sees its output.
- {"type": "applescript", "script": "tell application \\"Music\\" to playpause"}: runs with osascript in the background.
- {"type": "page", "page": "media"}: show another page; "back" returns to the previous one.
- {"type": "screen_brightness", "value": "+10", "display": "all"}: the Mac's displays. value "50" sets, "+10" / "-10" changes; display all, builtin or external (external monitors need DDC/CI on).
- {"type": "brightness", "value": "+10"}: the DisplayPad's own backlight, same values.
- {"type": "delay", "ms": 300}: wait between two actions (e.g. open an app, then send it a shortcut).
- {"type": "configurator"}: open the DisplayPad configurator in the browser.
- {"type": "obs", "do": "record"}: controls OBS Studio through its WebSocket server, whichever app is in front (no hotkeys needed in OBS). do: stream (start/stop), record (start/stop), pause (the recording), scene (with "scene": a scene name, or "#2" for the second scene in OBS's Scenes list from the top), next_scene, previous_scene, mute (with "source": an audio source name; empty or missing: every microphone), virtualcam, studio (studio mode on/off), transition (studio mode: preview to program), replay (save the replay buffer). In studio mode scene changes go to the preview. The user sets up the connection in the configurator, Settings > OBS (turn on OBS's WebSocket server and enter its password; you never see it). get_obs_info tells whether OBS can be reached and lists its scenes and sources.
- {"type": "sound", "file": "sounds/applause-1a2b3c.mp3", "volume": 80, "play": "restart"}: plays a sound through the Mac's sound output, for soundboard keys. file: a path returned by upload_sound, one of list_sounds (the sounds already added, and the Mac's alert sounds such as "/System/Library/Sounds/Glass.aiff"), or any file on the Mac ("~/Music/intro.mp3"); MP3, M4A/AAC, WAV, AIFF, CAF or FLAC. volume: 0-100 (default 100). play, for a press while the sound still plays: "restart" (default: from the start again), "toggle" (stops it), "overlap" (another copy on top). While it plays, a ring around the key shows how far it has got. Label sound keys with the sound's name.
- {"type": "stop_sounds"}: stops every sound playing (a soundboard's Stop key).
- {"type": "macro", "steps": [...], "play": "once", "delays": "recorded"}: plays keyboard and mouse steps in order. The user usually records one in the configurator (Record… on a Macro action); you cannot record, but you can write or edit the steps:
  {"do": "keys", "keys": "cmd+c"} a whole shortcut (same names as "shortcut"); {"do": "key_down", "key": "rcmd"} / {"do": "key_up", "key": "rcmd"} one key held and let go; {"do": "text", "text": "Hello"};
  {"do": "click", "button": "left", "count": 2, "x": 640, "y": 400} (no x/y: where the pointer is); {"do": "mouse_down", "button": "right", "x": .., "y": ..} / {"do": "mouse_up", ...}; {"do": "move", "x": .., "y": ..} (drags while a button is down); {"do": "scroll", "dy": -120, "dx": 0} (pixels, positive dy scrolls up, optional x/y); {"do": "wait", "ms": 250}.
  Buttons: left, right, middle, back, forward. x/y are screen points from the top-left of the main display. At most 5000 steps, and at least one that is not a wait.
  play: "once"; "repeat" with "times" (1-1000); "while_held" (at least once, then again while the pad key is held); "toggle" (one press starts it looping, the next stops it). delays: "recorded" (the waits as written), "fixed" with "delay_ms" (that wait between all steps instead), "none" (as fast as possible). Pressing the key again while a macro plays does nothing, except to stop a "toggle" one. Keys and buttons it holds are let go when it ends or is stopped.

PERMISSIONS
- shortcut, text, media and macro need the macOS Accessibility permission for Python. If get_status shows "accessibility": false, tell the user to allow it in System Settings > Privacy & Security > Accessibility.

GOOD PRACTICE
- Short labels, one idea per key, related keys on the same page. Every extra page needs a way back (create_page puts a "back" key on key 1) and a key on another page that leads to it.
- When 12 keys are not enough, a folder keeps related keys one press away and comes with its own Back key; it is simpler than a new page.
- Dark, saturated backgrounds keep the white label readable.
- For web apps, "open" with the URL is simpler than a chain of shortcuts; add "reuse_tab": true so a second press goes back to the tab.
- For multi-step automations prefer one AppleScript or shell action over many shortcuts and delays. When the user wants to repeat what they do by hand, suggest recording a macro in the configurator; in macros you write, prefer keys and text steps over clicks at fixed positions, which break when a window moves.
- test_actions on a macro waits 3 seconds first (time for the user to switch apps), then plays it once.
- After changing keys, check them with preview_page."""

PAGE = {"type": "string", "description": "Page name, or a folder as \"<page>/<key>\" (e.g. \"home/3\", \"home/3/5\"), "
                                          "as listed by list_pages."}
TOP_PAGE = {"type": "string", "description": "Page name, as listed by list_pages (not a folder)."}
KEY = {"type": "integer", "minimum": 1, "maximum": 12,
       "description": "Key number: 1-6 top row, 7-12 bottom row, left to right."}
ACTION = {"type": "object", "required": ["type"], "description": "One action; see get_reference.",
          "properties": {"type": {"type": "string", "enum": ["open", "shortcut", "text", "media", "shell", "applescript",
                                                             "page", "screen_brightness", "brightness", "delay",
                                                             "configurator", "macro", "obs", "sound", "stop_sounds"]},
                         "browser": {"type": "string", "description": "open with a web address: a browser from list_browsers."},
                         "new": {"type": "string", "enum": ["tab", "window"], "description": "open with a web address: default tab."},
                         "reuse_tab": {"type": "boolean", "description": "open with a web address: go to the tab already showing it."}}}
KEY_SPEC = {
    "type": "object", "description": "How the key looks and what it does; see get_reference.",
    "properties": {
        "emoji": {"type": "string"},
        "image": {"type": "string", "description": "icons/... path returned by upload_image."},
        "label": {"type": "string"},
        "hide_label": {"type": "boolean"},
        "color": {"type": "string", "description": "Background, #RRGGBB."},
        "text_color": {"type": "string", "description": "Label color, #RRGGBB."},
        "background": {"type": "object", "description": "A gradient background, still or moving; see get_reference.",
                       "properties": {"style": {"type": "string", "enum": list(render.BG_STYLES)},
                                      "colors": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3},
                                      "angle": {"type": "number", "minimum": 0, "maximum": 360},
                                      "speed": {"type": "number", "minimum": render.SPEED_MIN, "maximum": render.SPEED_MAX}}},
        "press_effect": {"type": "object", "description": "Animation played over the key when pressed; see get_reference.",
                         "properties": {"style": {"type": "string", "enum": list(render.EFFECTS)},
                                        "color": {"type": "string", "description": "#RRGGBB, default #FFFFFF."}},
                         "required": ["style"]},
        "fill": {"type": "boolean"},
        "icon_scale": {"type": "number", "minimum": 30, "maximum": 200},
        "crop": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
                 "description": "[left, top, right, bottom], fractions of the picture; see get_reference."},
        "actions": {"type": "array", "items": ACTION},
        "folder": {"type": "object", "description": "Makes the key a folder: {\"keys\": {\"2\": spec, ...}}; see get_reference."},
        "live": {"type": "object", "description": "Shows something that keeps changing (the label is its text, with {values}); see get_reference.",
                 "properties": {"source": {"type": "string", "enum": list(live.SOURCES)},
                                "style": {"type": "string", "enum": list(live.STYLES)},
                                "alert": {"type": "boolean"},
                                "command": {"type": "string"}, "every": {"type": "number", "minimum": live.COMMAND_MIN,
                                                                           "maximum": live.COMMAND_MAX}},
                 "required": ["source"]},
    },
}


class ToolError(Exception):
    """Shown to the assistant as a failed tool call (isError), not a protocol error."""


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- helpers
def _key(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise ToolError("key must be a number from 1 to 12")
    if not 1 <= n <= 12:
        raise ToolError("key must be a number from 1 to 12")
    return str(n)


def _page(raw: dict, name) -> dict:
    """The page, or the folder for "<page>/<key>/...": the object that holds "keys"."""
    pages = raw.get("pages") or {}
    pname, *path = str(name).split("/")
    if pname not in pages:
        raise ToolError(f"there is no page '{pname}'. Pages: {', '.join(pages) or 'none'}")
    if not isinstance(pages[pname], dict):
        pages[pname] = {}
    box, where = pages[pname], pname
    for kn in path:
        spec = (box.get("keys") or {}).get(kn) if isinstance(box.get("keys"), dict) else None
        if not isinstance(spec, dict) or not isinstance(spec.get("folder"), dict):
            raise ToolError(f"key {kn} of '{where}' is not a folder (list_pages lists the folders)")
        box, where = spec["folder"], f"{where}/{kn}"
    return box


def _top_page(raw: dict, name) -> dict:
    if "/" in str(name):
        raise ToolError(f"'{name}' is a folder; this needs a page")
    return _page(raw, name)


def _slot(name, n) -> str:
    """A key number, refusing key 1 of a folder (its fixed Back key)."""
    k = _key(n)
    if "/" in str(name) and k == "1":
        raise ToolError("key 1 of a folder is its Back key and cannot be changed; use keys 2 to 12")
    return k


def _walk(raw: dict):
    """(page or folder id, key number, key) for every key, folders included."""
    def walk(where, keys):
        for kn, spec in (keys.items() if isinstance(keys, dict) else ()):
            if isinstance(spec, dict):
                yield where, kn, spec
                if isinstance(spec.get("folder"), dict):
                    yield from walk(f"{where}/{kn}", spec["folder"].get("keys"))
    for pn, p in (raw.get("pages") or {}).items():
        yield from walk(pn, (p or {}).get("keys"))


def _folder_size(spec: dict) -> int:
    return sum(1 for v in ((spec.get("folder") or {}).get("keys") or {}).values() if v)


def _save(svc, change) -> str:
    try:
        return svc.update_config(change)
    except daemon.ConfigError as e:
        raise ToolError(f"not saved: {e}")


def _actions(spec: dict) -> list:
    return actions.actions_of(spec or {})


def _act_summary(a: dict) -> str:
    if a.get("type") == "macro":
        steps = a.get("steps") if isinstance(a.get("steps"), list) else []
        n = sum(1 for s in steps if isinstance(s, dict) and s.get("do") != "wait")
        play = a.get("play") or "once"
        return f"macro: {n} step(s), {play}" + (f" x{a.get('times')}" if play == "repeat" else "")
    if a.get("type") == "obs":
        extra = a.get("scene") or a.get("source") or ""
        return f"obs: {a.get('do')}" + (f" {json.dumps(extra, ensure_ascii=False)}" if extra else "")
    return (f"{a.get('type')}: {next((str(v) for k, v in a.items() if k != 'type'), '')}".rstrip(": ")
            + (" (held)" if a.get("hold") else ""))


def _summary(spec: dict) -> str:
    lv = spec.get("live") if isinstance(spec.get("live"), dict) else None
    look = " ".join(x for x in (spec.get("emoji"), spec.get("image") and f"[{os.path.basename(spec['image'])}]",
                                spec.get("label") and json.dumps(spec["label"], ensure_ascii=False),
                                lv and f"[live {lv.get('source')}{' meter' if lv.get('style') == 'meter' else ''}]") if x)
    acts = "; ".join(_act_summary(a) for a in _actions(spec) if isinstance(a, dict))
    if isinstance(spec.get("folder"), dict):
        return (look or "(no icon)") + f" -> folder with {_folder_size(spec)} key(s)" + (f", after: {acts}" if acts else "")
    return (look or "(no icon)") + (f" -> {acts}" if acts else " -> does nothing")


def _check_image(svc, spec: dict):
    img = spec.get("image")
    if img and not os.path.isfile(os.path.join(svc.cfg["base_dir"], os.path.expanduser(img))):
        raise ToolError(f"image '{img}' not found: add it with upload_image and use the path it returns")


def _live_commands(spec: dict) -> set:
    """The commands of the live keys in a key and the folders inside it."""
    found = set()
    for _, _, s in _walk({"pages": {"x": {"keys": {"k": spec}}}}):
        lv = s.get("live")
        if isinstance(lv, dict) and lv.get("source") == "command" and isinstance(lv.get("command"), str):
            found.add(lv["command"].strip())
    return found


def _check_live_commands(svc, raw: dict, new: dict):
    """A live command runs by itself, every few seconds, without anyone pressing a key: an
    assistant may only add one when the user allowed it to run actions."""
    if svc.cfg["mcp"]["allow_run"]:
        return
    saved = set().union(*(_live_commands(s) for _, _, s in _walk(raw))) if raw else set()
    if _live_commands(new) - saved:
        raise ToolError("a live key with a command runs it by itself every few seconds, so it needs \"Allow running "
                        "actions\" on in DisplayPad Settings > AI assistants. Ask the user to turn it on, or to add the "
                        "command in the configurator (Live tab of the key).")


def _without_page_refs(raw: dict, name: str) -> list:
    """Drop "go to page <name>" actions from every key; returns the keys changed."""
    changed = []
    for pn, kn, spec in _walk(raw):
        acts = _actions(spec)
        keep = [a for a in acts if not (isinstance(a, dict) and a.get("type") == "page" and a.get("page") == name)]
        if len(keep) != len(acts):
            spec.pop("action", None)
            spec["actions"] = keep
            changed.append(f"{pn} key {kn}")
    return changed


# ---------------------------------------------------------------- tools
def get_status(svc, a):
    st = svc.status()
    st.pop("python_app", None)
    st["pages"] = [n for n in svc.cfg["pages"] if "/" not in n]
    st["folders"] = [n for n in svc.cfg["pages"] if "/" in n]
    st["start_page"] = svc.cfg["start_page"]
    return st


def get_reference(svc, a):
    return REFERENCE


def get_config(svc, a):
    return {"rev": svc.config_rev(), "config": svc.read_config()}


def list_pages(svc, a):
    raw = svc.read_config()
    pages = raw.get("pages") or {}
    start = raw.get("start_page") or next(iter(pages), None)
    out = []

    def add(name, box, folder_of=None):
        items = sorted(((box or {}).get("keys") or {}).items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 99)
        keys = {k: _summary(spec) for k, spec in items if isinstance(spec, dict) and spec}
        entry = {"name": name}
        if folder_of:
            entry["folder"] = folder_of
            keys = {"1": "Back (fixed)", **keys}
        else:
            entry["start_page"] = name == start
            if (box or {}).get("apps"):
                entry["opens_with"] = {"apps": box["apps"], "when": box.get("when", "open")}
        entry.update({"on_the_pad_now": name == svc.page,
                      "empty_keys": [n for n in range(1, 13) if str(n) not in keys], "keys": keys})
        out.append(entry)
        for k, spec in items:
            if isinstance(spec, dict) and isinstance(spec.get("folder"), dict):
                add(f"{name}/{k}", spec["folder"], spec.get("label") or spec.get("emoji") or f"key {k}")

    for name, p in pages.items():
        add(name, p)
    return out


def get_key(svc, a):
    k = _key(a["key"])
    if "/" in str(a["page"]) and k == "1":
        return {"page": a["page"], "key": 1, "spec": None, "note": "key 1 of a folder is its fixed Back key"}
    spec = (_page(svc.read_config(), a["page"]).get("keys") or {}).get(k)
    return {"page": a["page"], "key": int(k), "spec": spec or None}


def set_key(svc, a):
    k, spec, merge = _slot(a["page"], a["key"]), a["spec"], a.get("merge", False)
    if not isinstance(spec, dict):
        raise ToolError("spec must be an object")
    result = {}

    def change(raw):
        keys = _page(raw, a["page"]).setdefault("keys", {})
        old = keys.get(k) if isinstance(keys.get(k), dict) else {}
        if not merge and "folder" not in spec and _folder_size(old):
            raise ToolError(f"key {k} is a folder with {_folder_size(old)} key(s) inside; use merge true to change its "
                            "look, or clear_key to delete it with what is inside")
        new = dict(keys.get(k) or {}) if merge else {}
        if merge and ("actions" in spec or "action" in spec):
            new.pop("action", None)
            new.pop("actions", None)
        if merge and spec.get("image") and spec["image"] != new.get("image") and "crop" not in spec:
            new.pop("crop", None)  # a crop belongs to the picture it was made for
        for f, v in spec.items():
            if v is None:
                new.pop(f, None)
            else:
                new[f] = v
        _check_image(svc, new)
        _check_live_commands(svc, raw, new)
        if new:
            keys[k] = new
        else:
            keys.pop(k, None)
        result["spec"] = new or None

    _save(svc, change)
    return {"saved": True, "page": a["page"], "key": int(k), "spec": result["spec"],
            "note": "On the pad within a second if this page is showing (show_page switches it)."}


def clear_key(svc, a):
    k = _slot(a["page"], a["key"])

    def change(raw):
        (_page(raw, a["page"]).get("keys") or {}).pop(k, None)

    _save(svc, change)
    return {"cleared": True, "page": a["page"], "key": int(k)}


def create_page(svc, a):
    name = str(a["name"]).strip()
    if not name or name == "back" or "/" in name:
        raise ToolError("the page needs a name other than 'back', without “/”")
    keys = a.get("keys") or {}
    if not isinstance(keys, dict):
        raise ToolError("keys must be an object like {\"2\": {...}, \"3\": {...}}")
    back = a.get("back_key", True)

    def change(raw):
        pages = raw.setdefault("pages", {})
        if name in pages:
            raise ToolError(f"there is already a page '{name}'")
        new = {}
        if back:
            label = "Volver" if raw.get("language") == "es" else "Back"
            new["1"] = {"emoji": "⬅️", "label": label, "color": "#2B2B33",
                        "actions": [{"type": "page", "page": "back"}]}
        for kn, spec in keys.items():
            if isinstance(spec, dict):
                _check_image(svc, spec)
            new[_key(kn)] = spec
        pages[name] = {"keys": new}

    _save(svc, change)
    return {"created": name, "keys": sorted(int(k) for k in ([1] if back else []) + list(keys)),
            "next": f"add a key on another page with the action {{\"type\": \"page\", \"page\": \"{name}\"}} "
                    "so the user can reach it"}


def rename_page(svc, a):
    old, new = a["name"], str(a["new_name"]).strip()
    if not new or new == "back" or "/" in new:
        raise ToolError("the page needs a name other than 'back', without “/”")
    result = {}

    def change(raw):
        _top_page(raw, old)
        if new in raw["pages"] and new != old:
            raise ToolError(f"there is already a page '{new}'")
        raw["pages"] = {(new if n == old else n): p for n, p in raw["pages"].items()}
        refs = []
        for pn, kn, spec in _walk(raw):
            for act in _actions(spec):
                if isinstance(act, dict) and act.get("type") == "page" and act.get("page") == old:
                    act["page"] = new
                    refs.append(f"{pn} key {kn}")
        if raw.get("start_page") == old:
            raw["start_page"] = new
        result["links_updated"] = refs

    _save(svc, change)
    return {"renamed": old, "to": new, **result}


def link_page_to_apps(svc, a):
    name, when = a["page"], a.get("when", "open")
    names = [str(n).strip()[:-4] if str(n).strip().lower().endswith(".app") else str(n).strip()
             for n in (a.get("apps") or [])]
    names = list(dict.fromkeys(n for n in names if n))
    if when not in ("open", "front"):
        raise ToolError('when must be "open" or "front"')

    def change(raw):
        box = _top_page(raw, name)
        if names:
            box["apps"], box["when"] = names, when
        else:
            box.pop("apps", None)
            box.pop("when", None)

    _save(svc, change)
    installed = {appwatch.norm(n) for n in web.list_apps()}
    out = {"page": name, "apps": names, "when": when} if names else {"page": name, "apps": [], "linked": False}
    unknown = [n for n in names if appwatch.norm(n) not in installed]
    if unknown:
        out["note"] = f"not among the installed apps (still used, if that is the name of their .app): {', '.join(unknown)}"
    return out


def _lang(raw: dict) -> str:
    return "es" if raw.get("language") == "es" else "en"


def list_app_presets(svc, a):
    cat = presets.catalog(_lang(svc.read_config()), web.list_apps())
    return [{k: v for k, v in p.items() if k != "page"} for p in cat]


def add_app_preset(svc, a):
    p = presets.get(str(a["preset"]))
    if not p:
        raise ToolError(f"there is no preset '{a['preset']}'. Presets: {', '.join(x['id'] for x in presets.PRESETS)}")
    link = a.get("link", True)
    installed = web.list_apps()
    result = {}

    def change(raw):
        spec = presets.page(p, _lang(raw), installed)
        pages = raw.setdefault("pages", {})
        name = str(a.get("page") or "").strip()
        if name and name in pages:  # an existing page: the shortcuts it lacks, on its free keys
            box = _top_page(raw, name)
            keys = box.get("keys") if isinstance(box.get("keys"), dict) else box.setdefault("keys", {})
            have = {presets.action_id(act) for k in keys.values() if isinstance(k, dict)
                    for act in _actions(k) if isinstance(act, dict)}
            missing = [(n, k) for n, k in spec["keys"].items() if k["actions"][0]["type"] != "page"
                       and presets.action_id(k["actions"][0]) not in have]
            free = [str(i) for i in range(1, 13) if not keys.get(str(i))]
            later, added = [], []
            for n, k in missing:  # its own key number when free, else the first free key
                if n in free:
                    keys[n] = k
                    free.remove(n)
                    added.append(int(n))
                else:
                    later.append(k)
            for k in later:
                if not free:
                    break
                n = free.pop(0)
                keys[n] = k
                added.append(int(n))
            result.update(page=name, added_keys=sorted(added))
            if len(added) < len(missing):
                result["not_added"] = f"{len(missing) - len(added)} keys: the page has no more free keys"
            if len(missing) < len(spec["keys"]) - 1:
                result["already_there"] = len(spec["keys"]) - 1 - len(missing)
            if link:
                old = [n for n in (box.get("apps") or []) if isinstance(n, str)]
                known = set(map(appwatch.norm, old))
                box["apps"] = old + [n for n in spec["apps"] if appwatch.norm(n) not in known]
                box.setdefault("when", spec["when"])
        else:
            if not name:
                name, i = p["name"], 2
                while name in pages:
                    name, i = f"{p['name']} {i}", i + 1
            if name == "back" or "/" in name:
                raise ToolError("the page needs a name other than 'back', without “/”")
            if not link:
                spec.pop("apps")
                spec.pop("when")
            pages[name] = spec
            result.update(page=name, created=True, keys=sorted(int(k) for k in spec["keys"]))
        box = pages[name]
        if box.get("apps"):
            result.update(apps=box["apps"], when=box.get("when", "open"))

    _save(svc, change)
    if result.get("created"):
        result["note"] = f"key {presets.BACK_KEY} goes back to the previous page"
    return result


def delete_page(svc, a):
    name = a["name"]
    result = {}

    def change(raw):
        _top_page(raw, name)
        if len(raw["pages"]) == 1:
            raise ToolError("this is the only page; it cannot be deleted")
        del raw["pages"][name]
        result["links_removed"] = _without_page_refs(raw, name)
        if raw.get("start_page", name) == name:
            raw["start_page"] = next(iter(raw["pages"]))

    _save(svc, change)
    return {"deleted": name, **result}


def show_page(svc, a):
    name = a["page"]
    _page(svc.read_config(), name)
    end = time.monotonic() + 3
    while name not in svc.cfg["pages"] and time.monotonic() < end:  # just created: wait for the reload
        time.sleep(0.1)
    svc.request_page(name)
    return {"showing": name, "pad_connected": svc.pad.connected}


def update_settings(svc, a):
    patch = {f: a[f] for f in ("language", "theme", "brightness", "press_feedback", "corner_radius")
             if a.get(f) is not None}
    if a.get("start_page") is not None:
        def change(raw):
            _top_page(raw, a["start_page"])
            raw["start_page"] = a["start_page"]
        _save(svc, change)
    if patch:
        try:
            svc.update_settings(patch)
        except daemon.ConfigError as e:
            raise ToolError(f"not saved: {e}")
    if not patch and a.get("start_page") is None:
        raise ToolError("give at least one setting to change")
    return {"saved": True, **patch, **({"start_page": a["start_page"]} if a.get("start_page") else {})}


def test_actions(svc, a):
    if not svc.cfg["mcp"]["allow_run"]:
        raise ToolError("Running actions from an assistant is turned off. Save the actions on a key and let the user "
                        "press it, or ask the user to turn on \"Let assistants run actions\" in the DisplayPad app, "
                        "Settings > AI assistants.")
    acts = a["actions"]
    if not isinstance(acts, list) or not acts:
        raise ToolError("actions must be a non-empty list")
    log.info("MCP: running %d action(s) on request of an assistant", len(acts))
    results = actions.test_actions({"actions": acts}, svc, svc.read_config().get("pages") or {})
    if len(results) < len(acts):
        results.append({"note": "the remaining actions were not run because one failed"})
    return results


def get_obs_info(svc, a):
    return obs.info(svc.cfg["base_dir"])


def list_apps(svc, a):
    return web.list_apps()


def list_browsers(svc, a):
    b = browsers.installed(fresh=True)
    return {"default": b["default"]["name"] if b["default"] else None,
            "browsers": [{"name": x["name"], "new_window_and_reuse_tab": x["tabs"]} for x in b["browsers"]]}


def upload_image(svc, a):
    if a.get("file_path"):
        path = os.path.expanduser(a["file_path"])
        if not os.path.isfile(path):
            raise ToolError(f"file not found: {path}")
        if os.path.getsize(path) > MAX_UPLOAD:
            raise ToolError("file too large (12 MB max)")
        with open(path, "rb") as f:
            data = f.read()
    elif a.get("data_base64"):
        b64 = a["data_base64"]
        b64 = b64.split(",", 1)[1] if b64.startswith("data:") else b64
        try:
            data = base64.b64decode(b64, validate=False)
        except ValueError as e:
            raise ToolError(f"data_base64 is not valid base64: {e}")
        if len(data) > MAX_UPLOAD:
            raise ToolError("file too large (12 MB max)")
    else:
        raise ToolError("give file_path (a file on this Mac) or data_base64")
    try:
        rel = web.save_upload(data, svc.cfg["base_dir"])
    except ValueError as e:
        raise ToolError(str(e))
    from PIL import Image
    with Image.open(os.path.join(svc.cfg["base_dir"], rel)) as img:
        w, h = img.size
    out = {"image": rel, "width": w, "height": h, "next": "use it as the \"image\" field of a key with set_key"}
    if w != h:
        out["note"] = ("Not square: without \"crop\" the middle of the picture covers the key (on a key with visible text it is shown whole). "
                       "Set crop to choose the part to show, or to show it whole (see get_reference).")
    return out


def upload_sound(svc, a):
    name = os.path.basename(str(a.get("name") or a.get("file_path") or ""))
    if a.get("file_path"):
        path = os.path.expanduser(a["file_path"])
        if not os.path.isfile(path):
            raise ToolError(f"file not found: {path}")
        if os.path.getsize(path) > sound.MAX_UPLOAD:
            raise ToolError("the sound is too large (50 MB max)")
        with open(path, "rb") as f:
            data = f.read()
    elif a.get("data_base64"):
        if not name:
            raise ToolError("give name (the file's name with its type, e.g. \"applause.mp3\") with data_base64")
        b64 = a["data_base64"]
        b64 = b64.split(",", 1)[1] if b64.startswith("data:") else b64
        try:
            data = base64.b64decode(b64, validate=False)
        except ValueError as e:
            raise ToolError(f"data_base64 is not valid base64: {e}")
    else:
        raise ToolError("give file_path (a file on this Mac) or data_base64 with name")
    try:
        out = sound.save_upload(data, name, svc.cfg["base_dir"])
    except ValueError as e:
        raise ToolError(str(e))
    return {**out, "next": "use it as the \"file\" of a {\"type\": \"sound\"} action with set_key"}


def list_sounds(svc, a):
    return sound.list_sounds(svc.cfg["base_dir"])


def preview_page(svc, a):
    try:
        cfg = daemon.parse_config(svc.read_config(), svc.cfg["base_dir"])
    except daemon.ConfigError as e:
        raise ToolError(str(e))
    name = a.get("page") or svc.page
    if name not in cfg["pages"]:
        raise ToolError(f"there is no page '{name}'. Pages: {', '.join(cfg['pages'])}")
    lives = [s["live"] for s in cfg["pages"][name] if s and "live" in s]
    if lives:  # take readings for its live keys (up to 2 s for the first ones)
        svc.live.watch("preview", lives, ttl=live.LOOKER_TTL)
        end = time.monotonic() + 2
        while not svc.live.ready(lives) and time.monotonic() < end:
            time.sleep(0.1)
    buf = io.BytesIO()
    render.preview_sheet(cfg["pages"][name], cfg["base_dir"], cfg["corner_radius"], live=svc.live.face).save(buf, "PNG")
    return [{"type": "text", "text": f"Page '{name}' as the DisplayPad draws it: keys 1-6 top row, 7-12 bottom row "
                                     "(animated keys show their first frame" + (", live keys their reading now" if lives else "") + ")."},
            {"type": "image", "data": base64.b64encode(buf.getvalue()).decode(), "mimeType": "image/png"}]


def _tool(fn, title, description, props=None, required=(), read_only=False, destructive=False, open_world=False):
    return {"fn": fn, "name": fn.__name__, "title": title, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}, "required": list(required),
                            "additionalProperties": False},
            "annotations": {"title": title, "readOnlyHint": read_only, "destructiveHint": destructive,
                            "idempotentHint": read_only, "openWorldHint": open_world}}


TOOLS = [
    _tool(get_status, "DisplayPad status",
          "Whether the DisplayPad is connected, the page it shows, brightness, macOS permissions "
          "(input_monitoring, accessibility), the pages and the start page.", read_only=True),
    _tool(get_reference, "Configuration reference",
          "Every key field and action type with examples, plus layout tips. Read it before creating keys.",
          read_only=True),
    _tool(get_config, "Read the whole configuration", "The full config.json (all pages and keys) and its revision.",
          read_only=True),
    _tool(list_pages, "List pages and keys",
          "Each page and folder (\"<page>/<key>\") with a one-line summary of every key (icon, label, actions), "
          "its empty keys and which page is the start page or on the pad now.", read_only=True),
    _tool(get_key, "Read one key", "The full settings of one key.", {"page": PAGE, "key": KEY}, ("page", "key"),
          read_only=True),
    _tool(set_key, "Set up a key",
          "Save how a key looks and what it does. Replaces the key unless merge is true (then only the given "
          "fields change; a field set to null is removed). The page must exist (create_page).",
          {"page": PAGE, "key": KEY, "spec": KEY_SPEC,
           "merge": {"type": "boolean", "description": "Change only the given fields. Default false."}},
          ("page", "key", "spec"), destructive=True),
    _tool(clear_key, "Clear a key", "Make a key empty (no icon, no actions).", {"page": PAGE, "key": KEY},
          ("page", "key"), destructive=True),
    _tool(create_page, "Create a page",
          "Add a page. By default key 1 becomes a \"back\" key. Optionally fill keys at once.",
          {"name": {"type": "string"},
           "keys": {"type": "object", "description": "Optional {\"2\": spec, \"3\": spec, ...}.",
                    "additionalProperties": KEY_SPEC},
           "back_key": {"type": "boolean", "description": "Put a back key on key 1. Default true."}},
          ("name",)),
    _tool(rename_page, "Rename a page", "Rename a page; keys that lead to it are updated.",
          {"name": TOP_PAGE, "new_name": {"type": "string"}}, ("name", "new_name")),
    _tool(delete_page, "Delete a page", "Delete a page and the \"go to this page\" actions that lead to it.",
          {"name": TOP_PAGE}, ("name",), destructive=True),
    _tool(link_page_to_apps, "Open a page with apps",
          "Make a page come up on the pad by itself, like a profile: when one of the apps opens (when \"open\", "
          "back when the last one quits) or while one is in front (when \"front\", back when another app comes "
          "to the front). An empty apps list removes the link.",
          {"page": TOP_PAGE,
           "apps": {"type": "array", "items": {"type": "string"}, "description": "App names, as list_apps gives them."},
           "when": {"type": "string", "enum": ["open", "front"], "description": "Default \"open\"."}},
          ("page", "apps")),
    _tool(list_app_presets, "List ready-made app pages",
          "Ready-made pages with the most-used shortcuts of popular apps (Photoshop, Premiere Pro, DaVinci "
          "Resolve, Figma, VS Code, Zoom…) and OBS controls: each one's id, its apps, which are installed, its "
          "keys, and \"setup\" when the app needs something turned on first (obs: Settings > OBS).",
          read_only=True),
    _tool(add_app_preset, "Add a ready-made app page",
          "Create a page from a preset (list_app_presets), linked to the app so it comes up while the app is in "
          "front (OBS: while it is open). With the name of an existing page, add the preset's keys that page "
          "lacks to its free keys instead (nothing is replaced).",
          {"preset": {"type": "string", "description": "Preset id from list_app_presets, e.g. \"photoshop\"."},
           "page": {"type": "string", "description": "Name for the new page (default: the app's name), or an "
                                                      "existing page to add the shortcuts to."},
           "link": {"type": "boolean", "description": "Link the page to the app (shown while it is in front, "
                                                      "or open for OBS). Default true."}},
          ("preset",)),
    _tool(show_page, "Show a page on the pad", "Switch the DisplayPad to a page or folder now.", {"page": PAGE}, ("page",)),
    _tool(update_settings, "Change general settings",
          "Pad backlight brightness (0-100), darken-on-press, rounded key corners (corner_radius: pixels "
          "on the 102-pixel key face, 0 square, 12 default, 51 round), start page, and the configurator's language "
          "(en, es) and theme (system, light, dark).",
          {"brightness": {"type": "integer", "minimum": 0, "maximum": 100},
           "press_feedback": {"type": "boolean"},
           "corner_radius": {"type": "integer", "minimum": 0, "maximum": 51},
           "start_page": TOP_PAGE,
           "language": {"type": "string", "enum": ["en", "es"]},
           "theme": {"type": "string", "enum": ["system", "light", "dark"]}}),
    _tool(test_actions, "Run actions now",
          "Run a list of actions immediately on this Mac and report each result (shell and AppleScript output "
          "included), to test an automation before saving it on a key. Only works if the user allowed it.",
          {"actions": {"type": "array", "items": ACTION, "minItems": 1}}, ("actions",),
          destructive=True, open_world=True),
    _tool(get_obs_info, "Check OBS",
          "Whether DisplayPad can reach OBS Studio (Settings > OBS), with OBS's scenes (top first), the current "
          "scene, studio mode, and its audio sources and microphones, for \"obs\" actions.", read_only=True),
    _tool(list_apps, "List installed apps", "Names of the apps installed on this Mac, for \"open\" actions and link_page_to_apps.",
          read_only=True),
    _tool(list_browsers, "List browsers",
          "The web browsers on this Mac and the default one, for the \"browser\" of \"open\" actions with a web "
          "address, and whether each can open new windows and find an open tab (reuse_tab).", read_only=True),
    _tool(upload_image, "Add a picture or animation",
          "Store a picture (PNG, JPG, WebP), an animated GIF/WebP or a Lottie animation (.json, .lottie, .tgs) "
          "for keys. Returns the path to use as a key's \"image\".",
          {"file_path": {"type": "string", "description": "A file on this Mac."},
           "data_base64": {"type": "string", "description": "The file's bytes in base64 (a data: URL works too)."}}),
    _tool(upload_sound, "Add a sound",
          "Copy a sound file (MP3, M4A/AAC, WAV, AIFF, CAF or FLAC, up to 50 MB) into the configuration for "
          "soundboard keys. Returns the path to use as the \"file\" of a \"sound\" action, its name and its length.",
          {"file_path": {"type": "string", "description": "A file on this Mac."},
           "data_base64": {"type": "string", "description": "The file's bytes in base64 (a data: URL works too)."},
           "name": {"type": "string", "description": "The file's name with its type (e.g. \"applause.mp3\"); needed with data_base64."}}),
    _tool(list_sounds, "List sounds",
          "The sounds already added for sound keys (\"mine\", newest first, with their length) and the Mac's own "
          "alert sounds (\"mac\"), each with the \"file\" to use in a \"sound\" action.", read_only=True),
    _tool(preview_page, "Preview a page",
          "A picture of a page exactly as the DisplayPad draws it. Without page, the page on the pad now.",
          {"page": PAGE}, read_only=True),
]
TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}
TOOL_LIST = [{k: v for k, v in tool.items() if k != "fn"} for tool in TOOLS]


# ---------------------------------------------------------------- JSON-RPC
def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _call(svc, params: dict) -> dict:
    name, args = params.get("name"), params.get("arguments") or {}
    tool = TOOLS_BY_NAME.get(name)
    if not tool:
        raise RpcError(-32602, f"Unknown tool: {name}")
    if not isinstance(args, dict):
        raise RpcError(-32602, "arguments must be an object")
    schema = tool["inputSchema"]
    unknown = [k for k in args if k not in schema["properties"]]
    missing = [k for k in schema["required"] if k not in args]
    if unknown or missing:
        msg = "; ".join(filter(None, [unknown and f"unknown argument(s): {', '.join(unknown)}",
                                      missing and f"missing argument(s): {', '.join(missing)}"]))
        return {"content": [{"type": "text", "text": msg}], "isError": True}
    log.info("MCP tool %s", name)
    try:
        out = tool["fn"](svc, args)
    except ToolError as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}
    except Exception as e:
        log.exception("MCP tool %s failed", name)
        return {"content": [{"type": "text", "text": f"{name} failed: {e}"}], "isError": True}
    if isinstance(out, list) and out and isinstance(out[0], dict) and "type" in out[0] and name == "preview_page":
        return {"content": out, "isError": False}
    text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1)
    return {"content": [{"type": "text", "text": text}], "isError": False}


def handle(msg, svc):
    """Answer one JSON-RPC message; None for notifications and responses."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    method = msg.get("method")
    if not isinstance(method, str) or "id" not in msg:
        return None  # notifications/initialized, notifications/cancelled, or a reply: nothing to answer
    mid, params = msg["id"], msg.get("params") or {}
    try:
        if method == "initialize":
            asked = params.get("protocolVersion")
            result = {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "displaypad-mac", "title": "DisplayPad for Mac", "version": __version__},
                      "instructions": INSTRUCTIONS}
            log.info("MCP: %s connected (protocol %s)",
                     (params.get("clientInfo") or {}).get("name", "an assistant"), result["protocolVersion"])
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOL_LIST}
        elif method == "tools/call":
            result = _call(svc, params)
        else:
            return _error(mid, -32601, f"Method not found: {method}")
    except RpcError as e:
        return _error(mid, e.code, str(e))
    return {"jsonrpc": "2.0", "id": mid, "result": result}


# ---------------------------------------------------------------- stdio bridge
def _out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def stdio_bridge(base_dir: str) -> int:
    """`python -m displaypad_mac mcp`: newline-delimited JSON-RPC on stdin/stdout, forwarded
    to the service's /mcp with the access key, so the key never goes in the app's settings."""
    token_path = os.path.join(base_dir, ".mcp-token")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError as e:
            _out(_error(None, -32700, f"Parse error: {e}"))
            continue
        ids = [m["id"] for m in (msg if isinstance(msg, list) else [msg])
               if isinstance(m, dict) and "id" in m and "method" in m]
        try:
            with open(token_path) as f:
                token = f.read().strip()
        except OSError:
            token = ""
        req = urllib.request.Request(web.mcp_url(), data=line.encode(), method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + token})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            reply = json.loads(data) if data.strip() else None
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read())["error"]
            except (ValueError, KeyError, TypeError):
                err = {"code": -32603, "message": f"DisplayPad service answered HTTP {e.code}"}
            reply = [{"jsonrpc": "2.0", "id": i, "error": err} for i in ids]
        except (urllib.error.URLError, OSError, ValueError) as e:
            err = {"code": -32603, "message": "the DisplayPad service is not running (open the DisplayPad app, "
                                              f"or run install.sh again): {e}"}
            reply = [{"jsonrpc": "2.0", "id": i, "error": err} for i in ids]
        if isinstance(reply, list) and not isinstance(msg, list):
            reply = reply[0] if reply else None
        if reply:
            _out(reply)
    return 0
