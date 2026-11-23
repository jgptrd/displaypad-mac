# DisplayPad for Mac

Use the **Mountain DisplayPad** (USB `3282:0009`) on macOS, without BaseCamp: a picture
or animation on each of the 12 keys, several pages, and one or more actions per key
(open apps, keyboard shortcuts, typed text, media keys, macros, scripts, screen brightness).
It runs as a background service and comes with a **visual configurator** in the browser
and an optional **MCP server**, so an AI assistant can help you set up your keys.

[Español](README.es.md)

![The configurator starting up: the DisplayPad rises in the middle of the screen, its 12 keys light up and it flies to its place on the page](docs/intro.gif)

> **Made with AI.** This project was written with [Claude Code](https://claude.com/claude-code)
> (Anthropic's AI coding assistant), directed and tested by a person on a real DisplayPad.
> See [Made with AI](#made-with-ai).

## Features

- **12 keys with pictures:** emoji, PNG/JPG, animated GIF/WebP/APNG or **Lottie**
  (`.json`, `.lottie`, `.tgs`), with a label, colors and an icon size from 30 % to 200 %.
  You can **hide a key's text** without deleting it.
- **Gradient backgrounds and press effects:** a key's background can be a plain color, a
  two- or three-color gradient, a gradient that keeps flowing, or rolling waves, with
  ready-made gradients to start from. A press effect (ripple, flash, glow, sparkle, shine
  or bounce) plays over the key on the pad each time you press it.
- **Soundboard:** a key can play a sound file from your Mac (MP3, M4A, WAV, AIFF, CAF or
  FLAC) at its own volume, with a ring around the key that shows how far it has got.
  **New page → Soundboard** makes a page of sound keys with a Stop key in one go.
- **Pictures are never stretched:** keys are square, so a wide or tall picture opens a
  framing editor where you move and zoom it to choose the part the key shows, or show
  it whole. It works the same for GIF and Lottie animations.
- **Folders:** any key can be a folder with 11 more keys, and folders can go inside
  folders. Key 1 in a folder always takes you back.
- **Pages:** as many as you like, with a "back" key and a start page.
- **Pages that open with apps (profiles):** link a page to apps and the pad switches to it
  by itself, either while the app is open or while it is in front, and goes back when the
  app is gone.
- **Actions:** open an app, URL or folder, and a website in the browser you pick, in a
  new tab or window, or back in the tab where it is already open; keyboard shortcuts; type text; play/pause,
  volume and other media keys; play sounds; shell commands; AppleScript; change page; brightness of the
  Mac's screens (built-in and external over DDC/CI) and of the pad; pauses between actions.
  Several actions per key run in order.
- **OBS Studio:** start and stop streaming, recording and the virtual camera, switch
  scenes and mute microphones straight through OBS's WebSocket server, even while OBS is
  in the background and without setting up hotkeys in OBS.
- **Live keys:** a key can show something that keeps changing and redraw itself: the
  time and date, CPU, GPU and memory use, the battery, the volume and the microphone,
  what Music or Spotify is playing, whether OBS is live or recording, or a command's
  output. As text, or as a meter with the number, the last minute as a line and a bar
  that turns amber and red.
- **Macros:** record what you do with the keyboard and the mouse (keys, clicks, drags,
  scrolling), edit the steps and the delays, and play it from a key once, several times,
  while the key is held, or on and off with each press.
- **Configurator:** drag keys to swap them, drop pictures on them, record shortcuts
  (a single key, or left and right modifiers apart) or pick them on an on-screen keyboard,
  test actions and see their output before you save. English and Spanish, light and dark.
- **AI assistants (MCP):** Claude, Cursor, VS Code or any MCP app on your Mac can read
  and change your setup when you allow it. Off by default.
- **Service:** starts at login, reconnects by itself after sleep or unplugging, and
  reloads the configuration as soon as it changes.

## Requirements

- macOS. Tested on macOS 27.2 on Apple Silicon; Intel Macs should work but are untested.
- [Homebrew](https://brew.sh) and Python 3.11 or newer (`brew install python@3.14`).
- The installer adds `libusb` with Homebrew if it is missing.

## Install

Download the zip from the [latest release](../../releases/latest) and unzip it, or clone
the repository. Then, in Terminal:

```bash
cd displaypad-mac
./install.sh
```

The installer:

- copies the program to `~/Library/Application Support/DisplayPadMac/`;
- sets up its Python environment;
- registers a service that starts at login and restarts if it fails
  (`~/Library/LaunchAgents/com.displaypadmac.agent.plist`);
- adds the **DisplayPad** app to Applications. It opens the configurator.

Run `./install.sh` again to update. Your configuration is kept.

### Permissions

macOS asks for two permissions for **Python**. The installer prints the path of the
`Python.app` that needs them.

- **Input Monitoring:** without it the service cannot switch the DisplayPad on.
- **Accessibility:** needed by the shortcut, text, media key and macro actions, and to
  record shortcuts that macOS uses.

If macOS doesn't ask, open *System Settings → Privacy & Security*, open the section,
press **+** and choose that `Python.app`. Then press **Restart service** in the
configurator.

### Uninstall

```bash
./uninstall.sh
```

Add `--all` to also delete your configuration and pictures.

## The configurator

Open it with the **DisplayPad** app (Applications, Launchpad or Spotlight), with the
**⚙️ Configure** key on the pad, or with `python -m displaypad_mac configure`.

![The configurator: the 12 keys of a page on the left, the editor for key 1 on the right](docs/configurator-keys.png)


- **Pages:** tabs at the top. Create, rename and delete pages, mark the start page (★)
  or show a page on the pad.
- **Ready-made app pages:** **+ Page** and **+ App page** can start from an empty page
  or from the 9 to 11 most-used shortcuts of a popular app:
  - **Browsers:** Google Chrome, Microsoft Edge, Brave, Safari.
  - **Photo, video and sound:** Photoshop, Illustrator, Premiere Pro, After Effects,
    Lightroom Classic, DaVinci Resolve, Final Cut Pro, Logic Pro, Blender, Audacity.
  - **Work and chat:** Excel, Word, PowerPoint, Outlook, Slack, Discord, Zoom, Microsoft
    Teams.
  - **More:** Spotify, Figma, VS Code, Xcode, Obsidian.
  - **OBS Studio:** go live, record, pause, mic, virtual camera and scenes 1 to 5,
    through the OBS action (see the key editor below). It stays up while OBS is open, so
    you can use it from your game or another app.

  The apps you have come first. The page comes up while the app is in front, its key 12
  goes back, and every key is an ordinary shortcut you can change. Linking a page to one of these apps in **Open with apps…** also offers to add
  its shortcuts to the free keys, without replacing anything. Shortcuts are sent by key
  position and avoid punctuation keys, so they work with other keyboard layouts too.
- **Open with apps…:** pick the apps that bring the current page up on the pad, like a
  Base Camp profile, and when:
  - **While the app is open:** the page comes up when the app opens and goes away when it
    quits.
  - **While the app is in front:** the page comes up each time you switch to the app and
    goes away when you switch to another one.

  When the page goes away, the pad returns to what it showed before, unless you moved it
  to another page meanwhile. The configurator shows two pads: **Pages**, the ones you go
  to yourself, and under it **⚡ App pages**, the linked ones, each with its own tabs (with
  the app's name when the page name doesn't say it). Click a key on either pad to edit
  that page; drag a key onto the other pad to move it there. App names are compared
  without the year, so a page linked to "Adobe Photoshop" keeps working when "Adobe
  Photoshop 2027" arrives. Nothing changes until you press **Save**.
- **Keys:** click a key to edit it. Drag a key onto another to swap them, or drop a
  picture or a sound file on it. Copy and paste keys between pages.
- **The key editor:** the preview and the key's **Name** stay at the top; the rest is in
  tabs: **Style** (icon, size, background and press effect), **Actions** (what the key does; the tab shows
  how many), **Folder** and **Live**. The tab bar stays in view while you scroll, and the editor
  remembers the tab you were on when you pick another key.
- **Folders:** in the **Folder** tab, **Make this key a folder**, then **Open folder ›** (or
  double-click the key). Inside, key 1 is a fixed **Back** key and the path at the top
  (`home › Work`) takes you up. To move a key into a folder, drag it and hold it over the
  folder until it opens, then drop it where you want it. Holding it over **Back**, a step
  of the path or a page tab works the same way, and dropping it right on one of them
  puts it in the first free key there. On the pad, pressing a folder key opens it.
- **Style:** emoji, image or text only; icon size and colors. The emoji picker has your
  recent emoji and a suggested set; **Show all emoji** opens every emoji your Mac has
  (about 1,900), in groups. Search by name in English or Spanish, accents optional, and
  pick a skin tone. The names come from macOS itself, and the browser sorts and groups
  them, so nothing is downloaded and anything the picker offers, the pad can draw.
  Tick **Hide the name on the key** (under the name) to keep the name without drawing it.
  Under **Background** choose **Solid**, **Gradient**, **Moving** or **Waves** (see
  [Backgrounds and press effects](#backgrounds-and-press-effects)); under **When pressed**
  pick a press effect and **▶ Try it** to watch it on the preview.
  The preview is exactly what the pad draws.
- **Adjust framing:** when you add a picture or animation that isn't square, a window
  opens where you drag it and zoom it (slider, scroll wheel, trackpad pinch, or arrow
  keys and + / −) inside a square the size of the key. **Whole picture** shows all of it
  with the key color around it; **Fill the key** covers the key with its middle. The
  picture keeps its proportions; the original file is not changed, so you can reframe
  it later with **Adjust framing…** under **Image** in the Style tab.
- **Actions:** several per key, in order. **Record** captures the keys you press: a
  combination like ⌘⇧4, a single key like F13, or a modifier on its own, and it tells left
  from right (Right ⌘ is saved as `rcmd`). While it records, macOS and the other apps
  don't react to the keys, so system shortcuts like ⌘⇧4, ⌘Space, ⌘Tab or ⌘Q are recorded
  whole instead of running. The keyboard is back as soon as you let go of the keys, when
  you click elsewhere, or after 30 seconds. **Keyboard…** opens an on-screen keyboard to
  pick keys with the mouse, for example numeric keypad keys your keyboard doesn't have.
  **Hold the keys down while the pad key is held** is for apps
  that react to a held key, like push-to-talk dictation. **▶ Test** runs the actions and shows the output or error of shell commands and
  AppleScript.
- **Websites:** when an **Open** action has a web address, you can choose the **Browser**
  (the Mac's default or any browser installed), open it in **A new tab** (the default) or
  **A new window**, and tick **If it's already open, go to its tab**. With that on, a key
  for `https://web.whatsapp.com` brings back the WhatsApp tab you already have instead of
  opening a second one: a tab counts when its address starts with the key's, whatever
  comes after it, ignoring `http`/`https` and `www.`. Safari, Chrome, Edge, Brave and
  Vivaldi can do all of it; other browsers (Firefox, Arc, Opera) open the address like any
  link. The first time, macOS asks whether DisplayPad may control the browser. Typing a
  bare address like `web.whatsapp.com` adds `https://` for you.
- **Macros:** add a **Macro (keyboard and mouse)** action and press **● Record…**. Choose
  what to record (the keyboard, mouse clicks, drags and scrolling, and pointer moves if
  you need them) and press **Start recording**: you have 3 seconds to switch to your app.
  Do what the macro should do, then press any key on the DisplayPad (or **Stop** in the
  configurator). **Edit steps…** lists every step: change keys, buttons, positions and
  waits, add or move steps, or put the same wait everywhere. **Playback** plays it once,
  a number of times, while the pad key is held, or from one press to the next;
  **Delays** keeps the recorded waits, uses one fixed wait, or none. **▶ Test** plays it
  once after 3 seconds, and a banner with **Stop** shows while a macro is playing.
- **OBS Studio:** add an **OBS Studio** action and pick what it does: start or stop
  streaming, recording or the virtual camera, pause the recording, switch to a scene, go
  to the next or previous scene, mute or unmute microphones, studio mode, transition, or
  save the replay buffer. A scene is its name, or `#1` for the first scene in OBS's
  **Scenes** list, `#2` for the second, and so on, so a page keeps working when you rename
  scenes. Leave the audio source empty to mute every microphone at once. The editor lists
  your scenes and sources and says whether OBS can be reached. In studio mode, scene keys
  change the preview. Set up the connection first in **Settings → OBS**.
- **Live:** pick what the key shows (see [Live keys](#live-keys)). For a number (CPU,
  memory, battery…) choose **Text** or **Meter**. The values you can use in the key's
  **Name**, like `{time}` or `{value}`, are buttons that add them where the cursor is; the
  clock has quick formats. The previews on both pads update while you look at them.
- **Save** (⌘S) checks everything first and tells you which key has a problem. The
  previous file is kept as `config.json.previous`.

If something else changes the configuration while the configurator is open (an AI
assistant, or you editing `config.json`), the page reloads by itself. If you have unsaved
changes, it asks which version to keep.

### Settings

The **Settings** tab applies changes right away:

- **Language:** English (default) or Español.
- **Appearance:** same as macOS, light or dark.
- **DisplayPad:** key brightness, whether a key darkens while pressed, and the key corners.
  The pad's screens are square, so the service draws rounded corners into every picture,
  like the configurator shows them (12 px by default; 0 keeps them square).
- **OBS:** the connection to OBS Studio for the OBS keys. In OBS, choose **Tools →
  WebSocket Server Settings**, tick **Enable WebSocket server**, click **Show Connect
  Info** and copy the **Server Password** into **Password**. **Save and connect** saves it
  and shows OBS's version and scenes, or why it can't connect. The port is 4455 unless you
  changed it in OBS. The password is kept in `obs.json` next to the configuration, readable
  only by you, and never shown again in the configurator or to AI assistants.
- **AI assistants (MCP):** see below.
- **About:** version, service and permission status, and where the configuration and
  log are.

![The Settings tab: language, appearance, DisplayPad brightness and key corners, and the OBS connection](docs/configurator-settings.png)

## AI assistants (MCP)

DisplayPad for Mac includes a [Model Context Protocol](https://modelcontextprotocol.io)
server. When you allow it, an AI assistant on your Mac can look at your pages and keys,
create new ones, find the apps you have installed, add pictures and preview the result,
so you can ask things like *"Add a page with my meeting apps"* or *"Make a key that
mutes me in Zoom"*.

1. Open DisplayPad → **Settings** → **AI assistants** and tick **Allow AI assistants to
   connect**.
2. Connect your assistant. The Settings tab shows these snippets with your own paths and
   a **Copy** button.

**Claude Code:**

```bash
claude mcp add --scope user displaypad -- "$HOME/Library/Application Support/DisplayPadMac/displaypad-mcp"
```

**Claude Desktop:** *Settings → Developer → Edit Config*, add the entry and restart Claude.
Replace `YOU` with your macOS user name:

```json
{
  "mcpServers": {
    "displaypad": {
      "command": "/Users/YOU/Library/Application Support/DisplayPadMac/displaypad-mcp"
    }
  }
}
```

**Other apps:**

- Apps that start a local program (stdio): use the `displaypad-mcp` program above. It
  reads the access key by itself.
- Apps that connect to an address (Streamable HTTP): use `http://127.0.0.1:8765/mcp` and
  send the access key from Settings in the header `Authorization: Bearer <key>`.

The server only listens on this Mac, so assistants that run in the cloud and can't reach
`127.0.0.1` won't be able to connect.

| Tool | What it does |
|---|---|
| `get_status` | Connection, current page, permissions |
| `get_reference` | Every key field and action, with examples |
| `get_config`, `list_pages`, `get_key` | Read the setup |
| `set_key`, `clear_key` | Change or clear one key |
| `create_page`, `rename_page`, `delete_page` | Manage pages (links to a renamed or deleted page are updated) |
| `show_page` | Switch the pad to a page |
| `link_page_to_apps` | Make a page open by itself with apps (while open or while in front) |
| `list_app_presets`, `add_app_preset` | Ready-made pages with popular apps' shortcuts and OBS controls: create one, or add its keys to a page |
| `get_obs_info` | Whether OBS can be reached, with its scenes and audio sources |
| `update_settings` | Brightness, press feedback, language, appearance, start page |
| `list_apps` | Installed apps, for "open" actions and pages that open with apps |
| `list_browsers` | The browsers on this Mac and the default one, for "open" actions with a web address |
| `upload_image` | Add a picture or animation from a file or base64 |
| `upload_sound`, `list_sounds` | Add a sound for sound keys, or list the ones added and the Mac's own |
| `preview_page` | Picture of a page as the pad draws it, live keys included |
| `test_actions` | Run actions now (only if you allow it, see below) |

**Security**

- The server is off until you turn it on, only listens on `127.0.0.1`, needs the access
  key on every request and rejects requests from web pages.
- **New key** in Settings replaces the access key; connected assistants stop working
  until you give them the new one (the `displaypad-mcp` program picks it up by itself).
- Assistants save actions on keys, and those actions run when you press the key. Only
  connect assistants you trust, and check new keys that run shell commands or AppleScript.
- **Let assistants run actions right away** is off by default. While it is off,
  `test_actions` refuses to run anything, and an assistant can't add a live key that runs
  a new command (it can still add every other kind of live key).

## Animations (GIF and Lottie)

In **Image** you can upload or drop, besides pictures:

- **Animated GIF**, animated WebP or animated PNG (APNG).
- **Lottie:** `.json`, `.lottie` (dotLottie) or `.tgs` (Telegram stickers).

The DisplayPad doesn't store animations: it shows the last picture it got on each key, so
the service sends the frames one by one. Measured on the pad:

- **About 52 pictures per second in total** (about 18 ms each), shared by the animated
  keys of the page on screen.
- One animated key plays at the file's own speed: up to 50 frames per second for a GIF,
  25 for a Lottie. Two Lottie keys fit at full speed.
- If the animated keys ask for more than the pad can take, frames are skipped: each
  animation keeps its real speed but looks less smooth.
- While you hold an animated key down it stays still and darkened (a key with a press
  effect plays its effect instead and keeps moving).
- With the pad at its limit the service uses about 4 % CPU.

Uploads are stored in `icons/` as animated WebP, with the shorter side at most 204 px (so
the icon size can go up to 200 %) and the longer one at most 408 px (so a wide animation
can still be framed), and at most 180 frames (frames in between are dropped if there are more).
Lottie files are drawn with rlottie at 25 frames per second. Some After Effects features
(expressions, effects, text layers) may not be drawn; if a Lottie comes out without
motion the configurator tells you: export it as a GIF instead.

## Backgrounds and press effects

In the key editor's **Style** tab, **Background** has four styles:

- **Solid:** one color (the usual).
- **Gradient:** two or three colors blending across the key. **Direction** turns it
  (the arrow shows where it goes).
- **Moving:** the gradient's colors keep flowing along that direction.
- **Waves:** wavy bands of the colors that roll across the key.

Pick one of the ready-made gradients (Sunset, Ocean, Purple, Aurora, Fire, Mint, Candy,
Neon, Peach, Night, Royal blue) or your own colors; **+** adds a third color. **Moving**
and **Waves** have a **Speed** (slow, normal, fast). They play on the pad like an
animation, about 15 pictures per second each, and share the pad's speed with the other
animated keys of the page (see [Animations](#animations-gif-and-lottie)), so a page full
of moving keys moves less smoothly. With an animated picture on top, both play together
(the background's speed adjusts a little so the two loop together).
Meters, and live keys turning amber or red, keep a plain color.

**When pressed** sets a **press effect**, played over the key on the pad each time you
press it, in place of darkening it:

| Effect | What it does |
|---|---|
| Ripple | A ring spreads out from the middle |
| Flash | The key lights up and fades |
| Glow | The edge of the key lights up |
| Sparkle | A burst and little stars flying out |
| Shine | A band of light sweeps across |
| Bounce | The key is pushed in and springs back |

Every effect but Bounce has a color (white by default). The effect plays even with
**Darken a key while it is pressed** off in Settings. A key that opens a page or folder switches
at once, so its effect is cut short.

## Soundboard

A key can play a sound on your Mac. Add a **Play a sound** action (under **Sound** in the
action list) and give it a sound:

- **Choose a file…** picks one from your Mac, or drop a sound file on the action, or
  straight onto any key of the pad (a key with no look gets the sound's name and 🔊).
- **Pick a sound…** reuses a sound you added before, or one of the Mac's own sounds
  (Glass, Hero, Ping, Pop…).
- **File on this Mac** links a file wherever it is (`~/Music/intro.mp3`).

Files you choose are copied into DisplayPad's `sounds` folder, so the key keeps working if
you move or delete the original. MP3, M4A/AAC, WAV, AIFF, CAF and FLAC work, up to 50 MB.
**▶ Listen** plays it on the Mac and **■ Stop** stops it.

Each sound has a **Volume** (a share of the Mac's volume) and a choice for when you press
the key again while it still plays: **Play it again from the start** (the default),
**Stop it**, or **Play another copy on top**. While a sound plays, a ring around the key
fills up as it goes, so you can see what is playing and how much is left. A **Stop all
sounds** action stops everything.

Sounds play through the Mac's sound output (the one chosen in **System Settings → Sound**),
and keep playing if you switch pages.

**New page → Soundboard** builds a whole page at once: choose up to 10 sound files (or
none, to start with 10 of the Mac's sounds) and each gets a key with its name, a gradient
background and a ripple when pressed; key 11 stops every sound and key 12 goes back.

## Live keys

A live key shows a reading instead of a fixed name, and the service redraws it on the pad
by itself, only when what it shows changes. In the configurator, open a key's **Live** tab;
by hand, add `"live"` to the key (see [Key fields](#editing-the-configuration-by-hand)).

| `source` | What it shows | Values for the name | Read every |
|---|---|---|---|
| `clock` | Time and date | `{time}` (14:05), `{time12}` (2:05), `{ampm}`, `{seconds}`, `{weekday}`, `{day}`, `{month}`, `{year}`, `{date}` (Fri 20 Nov) | second |
| `cpu` | CPU use, all cores | `{value}` | 2 s |
| `gpu` | GPU use, as Activity Monitor's GPU History | `{value}` | 2 s |
| `ram` | Memory used, as Activity Monitor counts it | `{value}` (%), `{used}` (12.5 GB), `{total}` | 2 s |
| `battery` | Battery charge | `{value}`, `{state}` (charging, on battery…) | 30 s |
| `volume` | Output volume | `{value}`, `{state}` (muted) | 2 s |
| `mic` | Microphone input level | `{value}`, `{state}` (muted) | 2 s |
| `music` | What Music or Spotify is playing | `{title}`, `{artist}`, `{app}`, `{state}` | 3 s |
| `obs` | OBS Studio streaming and recording | `{status}` (LIVE · REC, Off air), `{scene}`, `{stream_time}`, `{record_time}` | 2 s |
| `command` | A shell command's output | `{output}` (its first line), `{value}` (the first number in it) | `every` seconds |

- **Text** (the default) draws the key's **Name** with the values in place, like
  `"{weekday} {day} {time}"`. With no name it shows the reading on its own
  (`{time}`, `CPU {value}%`, `{title}`…).
- **Meter** (`"style": "meter"`, for CPU, GPU, memory, battery, volume, microphone and
  commands) draws the name as a title, the number large, the last minute as a line and a
  bar. The bar turns amber at 70 % and red at 90 %; memory follows macOS's memory
  pressure instead, the battery turns amber at 20 % and red at 10 % unless it is
  charging, and volume and microphone meters turn grey while muted. The key's colors are used for the background and the text.
- **Alert:** text keys turn amber or red when the reading needs attention (OBS live or
  recording, the microphone muted, the sound muted, high CPU or GPU, a low battery, a
  command that fails). `"alert": false` turns that off.
- **Commands** run with `zsh -l` every `every` seconds (2 to 3600, 10 by default) and are
  stopped after 10 seconds. A meter uses the first number the command prints, from 0 to
  100. A command only runs once the key is saved, and the configurator's preview shows
  "save the key to run its command" until then.
- **What is playing:** only an app that is already open is asked, so a live key never
  opens Music or Spotify. The first time, macOS asks whether DisplayPad may control the
  app; if you said no, the key says so and you can allow it in **System Settings → Privacy
  & Security → Automation**.
- **OBS** uses the connection in **Settings → OBS** and is only asked while OBS is open.

Readings are only taken while a live key is on the pad or open in the configurator, each
source once for all the keys that show it. Live keys share the ≈ 52 pictures per second of
the pad with animations, but a live key only sends a picture when it changes: a clock
once a minute (once a second with `{seconds}`), a meter every 2 seconds. While you hold a
live key down it stays still and darkened.

## Editing the configuration by hand

You can also edit `~/Library/Application Support/DisplayPadMac/config.json`. **It is
reloaded as soon as you save it.** Keys are numbered 1 to 12: 1-6 on the top row and
7-12 on the bottom row. [`config.example.json`](config.example.json) is a full example.

```json
{
  "language": "en",
  "theme": "system",
  "brightness": 80,
  "press_feedback": true,
  "corner_radius": 12,
  "mcp": {"enabled": false, "allow_run": false},
  "start_page": "home",
  "pages": {
    "home": {
      "keys": {
        "1": {"emoji": "📧", "label": "Outlook", "color": "#0B3A66",
              "action": {"type": "open", "target": "Microsoft Outlook"}},
        "2": {"image": "icons/logo.png", "label": "Capture", "hide_label": true,
              "actions": [{"type": "shortcut", "keys": "cmd+shift+4"}]}
      }
    }
  }
}
```

`corner_radius` rounds the corners of every key picture, in pixels of the 102-pixel face:
`0` is square, `12` is the default, `51` is round.

A live clock and a CPU meter:

```json
"3": {"label": "{weekday} {day}\n{time}", "color": "#1C1C24", "live": {"source": "clock"}},
"4": {"label": "CPU", "live": {"source": "cpu", "style": "meter"},
      "actions": [{"type": "open", "target": "Activity Monitor"}]}
```

**Pages that open with apps:** a page can have `"apps"`, the names of the apps' `.app`
as the configurator lists them, and `"when"`: `"open"` (the default: shown while one of
them is open) or `"front"` (shown while one of them is in front). For example:
`"Photoshop": {"apps": ["Adobe Photoshop 2026"], "when": "front", "keys": {...}}`. The
service checks the open apps every second and the app in front every 0.4 seconds, and
needs no extra permission for it.

**Key fields** (all optional)

| Field | Meaning |
|---|---|
| `emoji` | An emoji, drawn in color |
| `image` | Path to a PNG, JPG, GIF or animated WebP, relative to the configuration folder (put pictures in `icons/`). Lottie files are converted when you upload them in the configurator |
| `crop` | Images only. `[left, top, right, bottom]`: the part of the picture the key shows, as fractions of its width and height (`[0.25, 0, 0.75, 1]` is the middle square of a 2:1 picture). Values below 0 or above 1 zoom out and show the key color there (`[0, -0.5, 1, 1.5]` shows a 2:1 picture whole). Never stretched: if the area isn't square in pixels, the picture is centred in it. Without `crop`, the middle of the picture covers the key, or, with a label or `fill: false`, the whole picture is shown. The configurator writes it for you |
| `fill` | Images only. `true` (default) makes a picture cover the whole key when no label is drawn; `false` keeps a margin |
| `icon_scale` | Size of the emoji or picture in %, 30 to 200 (100 is normal) |
| `label` | Text. It shrinks and wraps to fit |
| `hide_label` | `true` keeps the label without drawing it |
| `color` | Background color, e.g. `#1C1C24` |
| `text_color` | Text color |
| `background` | A [gradient background](#backgrounds-and-press-effects): `{"style": "waves", "colors": ["#FC5C7D", "#6A82FB"]}`. `style`: `gradient`, `animated` (moving), `waves` or `solid`; `colors`: 2 or 3; `angle`: degrees, 0 is up and 90 is right (default 135, waves 180); `speed`: 0.25 to 4 for `animated` and `waves` (default 1). `color` is still used by meters and alerts |
| `press_effect` | Played over the key when it is pressed: `{"style": "ripple", "color": "#FFFFFF"}`. `style`: `ripple`, `flash`, `glow`, `sparkle`, `shine` or `bounce`; `color` is optional |
| `action` / `actions` | One action, or a list run in order |
| `folder` | Makes the key a folder: `{"keys": {"2": {...}, "3": {...}}}`, with keys 2 to 12 (key 1 is its Back key). A folder can hold folders. Its own actions, if any, run before it opens |
| `live` | Makes it a [live key](#live-keys): `{"source": "cpu", "style": "meter"}`. `source` is required; `style` is `text` (default) or `meter`; `alert`: `false` keeps the colors; a `command` key also has `command` and `every` (seconds). The `label` is the text, with values like `{time}` in place |

**Actions**

| `type` | Fields | Example |
|---|---|---|
| `open` | `target`: app, URL or folder. For web addresses: `browser` (an app name; default: the Mac's default browser), `new`: `"tab"` (default) or `"window"`, `reuse_tab`: `true` goes to the tab already showing it | `"Microsoft Excel"`, `"~/Documents"`, `{"type": "open", "target": "https://web.whatsapp.com", "browser": "Google Chrome", "reuse_tab": true}` |
| `shortcut` | `keys`; `hold`: `true` keeps them down while the pad key is held | `"cmd+shift+4"`, `"f5"`, `"rcmd"`, `"ctrl+rshift"` |
| `text` | `text` (`\n` presses Return) | `"Best regards,\n"` |
| `media` | `key` | `play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`, `brightness_up`, `brightness_down` |
| `shell` | `command` | `"say done"` |
| `applescript` | `script` | `"display notification \"Hello\""` |
| `page` | `page`: a page name, or `back` | `"more"` |
| `screen_brightness` | `value`: a level or `"+10"` / `"-10"`; `display`: `all`, `builtin` or `external` | `{"value": "-10", "display": "all"}` |
| `brightness` | `value`: the pad's own brightness, a level or `"+10"` / `"-10"` | `"+20"` |
| `delay` | `ms`: wait between actions | `250` |
| `macro` | `steps`; `play`: `once`, `repeat` (with `times`), `while_held` or `toggle`; `delays`: `recorded`, `fixed` (with `delay_ms`) or `none` | see below |
| `configurator` | none: opens the configurator | |
| `obs` | `do`: `stream`, `record`, `pause`, `scene` (with `scene`), `next_scene`, `previous_scene`, `mute` (with `source`, empty for every microphone), `virtualcam`, `studio`, `transition`, `replay` | `{"do": "scene", "scene": "#2"}` |
| `sound` | `file`: in the configuration folder (`sounds/...`) or anywhere on the Mac; `volume`: 0 to 100 (default 100); `play` when pressed again while it plays: `restart` (default), `toggle` or `overlap` | `{"file": "sounds/applause-1a2b3c.mp3", "volume": 80}` |
| `stop_sounds` | none: stops every sound playing | |

`screen_brightness` changes the MacBook screen (like F1/F2) and external monitors over
DDC/CI (turn DDC/CI on in the monitor's menu if it doesn't respond).

`obs` talks to OBS Studio 28 or later through its WebSocket server (protocol 5), with the
connection set in **Settings → OBS**. `stream`, `record`, `pause`, `virtualcam` and
`studio` switch on and off with each press. A `scene` is a scene's name or `"#N"`, the
Nth scene from the top of OBS's **Scenes** list; `next_scene` and `previous_scene` follow
that list and go round. In studio mode scene changes go to the preview and `transition`
sends it to the program.

Shortcut modifiers: `cmd`, `shift`, `ctrl`, `alt`/`option`, `fn` (the left keys) and
`rcmd`, `rshift`, `rctrl`, `ralt` (the right ones). Keys: letters, numbers, `f1` to `f20`,
`return`, `tab`, `space`, `esc`, `delete`, `forwarddelete`, arrows (`up`, `down`, `left`,
`right`), `home`, `end`, `pageup`, `pagedown`, `help`, `section` (§), the numeric keypad
(`kp0` to `kp9`, `kpdecimal`, `kpplus`, `kpminus`, `kpmultiply`, `kpdivide`, `kpequals`,
`kpenter`, `kpclear`) and punctuation.

A shortcut can also be a single key (`"f13"`) or modifiers alone (`"rcmd"`), for apps
that start listening when you press one key. Add `"hold": true` to keep the keys down for
as long as you hold the pad key; they come up when you let go (after 10 minutes at most).
Without it, the keys are pressed and let go at once.

```json
{"type": "shortcut", "keys": "rcmd", "hold": true}
```

A macro is a list of steps played in order. The configurator records them for you, but
you can also write them:

| Step | Fields |
|---|---|
| `keys` | `keys`: a whole shortcut, pressed and let go (`"cmd+c"`) |
| `key_down`, `key_up` | `key`: one key or modifier (`"rcmd"`, `"a"`) |
| `text` | `text`: typed as is |
| `click` | `button` (`left`, `right`, `middle`, `back`, `forward`), `count` (2 is a double click), `x`, `y` |
| `mouse_down`, `mouse_up` | `button`, `x`, `y` |
| `move` | `x`, `y` (it drags while a button is down) |
| `scroll` | `dy`, `dx` in pixels (positive `dy` scrolls up), `x`, `y` |
| `wait` | `ms` |

`x` and `y` are screen points from the top-left corner of the main display; leave them
out to use wherever the pointer is. Pressing the key again while a macro plays does
nothing, except to stop a `toggle` one. Any key or button a macro holds is let go when it
ends or is stopped.

```json
{"type": "macro", "play": "repeat", "times": 3, "steps": [
  {"do": "keys", "keys": "cmd+a"}, {"do": "wait", "ms": 100},
  {"do": "text", "text": "Hello"}, {"do": "click", "x": 640, "y": 400}]}
```

## Useful commands

Run them from the installed folder:

```bash
cd ~/Library/Application\ Support/DisplayPadMac
```

| To… | Command |
|---|---|
| Open the configurator | `.venv/bin/python -m displaypad_mac configure` |
| Draw the pages as PNG files, without the device | `.venv/bin/python -m displaypad_mac preview --config config.json` |
| Check and request permissions | `.venv/bin/python -m displaypad_mac permissions` |
| Restart the service | `launchctl kickstart -k gui/$(id -u)/com.displaypadmac.agent` |
| Follow the log | `tail -f ~/Library/Logs/DisplayPadMac.log` |
| Test the hardware (stop the service first) | `.venv/bin/python -m displaypad_mac test` |

## Troubleshooting

- **`Cannot open DisplayPad IF0: kIOReturnNotPermitted`** in the log: Python is missing
  the Input Monitoring permission.
- **Shortcuts, text or media keys do nothing:** Python is missing the Accessibility
  permission.
- **It stopped working after `brew upgrade`:** Homebrew replaced the Python binary. Run
  `./install.sh` again and give the permissions to the new `Python.app`.
- **Keys stay black after the Mac sleeps or the pad is unplugged:** the service
  reconnects by itself in about 2 seconds. If it doesn't, restart it.
- **The DisplayPad app says the service is not responding:** check the log. If another
  program uses port 8765 the configurator can't start (the pad keeps working).
- **Screen − / + doesn't change the external monitor:** turn DDC/CI on in the monitor's
  menu. Some USB-C adapters and docks don't pass DDC through.
- **An animation stutters:** the animated keys on that page (moving and wave backgrounds
  count too) ask for more than the ≈ 52 pictures per second the pad accepts. Use fewer
  animated keys on that page, or GIFs with fewer frames per second.
- **A sound key is silent:** check the Mac's volume and which output is chosen in
  **System Settings → Sound**, and the key's **Volume**. **▶ Listen** in the action says if
  the file is missing. Bluetooth speakers can swallow the first moment of a short sound.
- **An AI assistant can't connect:** check that **Allow AI assistants to connect** is on
  and that the service is running. A `401` means the access key is wrong or was replaced.
- **OBS keys do nothing:** **Settings → OBS → Test connection** says why. OBS must be
  open with **Tools → WebSocket Server Settings → Enable WebSocket server** on, and the
  password must match the one in **Show Connect Info**.
- **A website key opens a new tab instead of going to the open one:** the **Try it**
  button under the action says why. Usually macOS asked whether DisplayPad may control the
  browser and it was refused: allow it in **System Settings → Privacy & Security →
  Automation**. The key only looks in the browser it opens (the default one unless you
  picked another), and the tab's address must start with the key's.
- **A "What is playing" key says to allow it in Settings:** macOS asked whether
  DisplayPad may control Music or Spotify and it was refused. Allow it in **System
  Settings → Privacy & Security → Automation**.
- **A live command key shows a dash or an error:** the preview shows the command's error;
  test the command in Terminal with `zsh -lc '...'`. Commands that take longer than 10
  seconds are stopped.
- **`Another DisplayPadMac instance is already running`:** only one program can use the
  DisplayPad at a time. Stop the service before using `test`.

## How it works

The Windows installer (BaseCamp 1.9.10) contains **no kernel driver**: no `.sys` or
`.inf` files. It is an Electron/.NET app whose `DisplayPadSDK.dll` talks to the device
through the standard Windows HID API. macOS already sees the DisplayPad as a HID
device, so all that was missing was a program that talks to it.

The device has three USB interfaces:

| Interface | What it is | How it is used on macOS |
|---|---|---|
| IF0 | HID keyboard (macOS drives it) | IOKit, shared open, one `SET_REPORT` |
| IF1 | Image data (no macOS driver) | claimed with `libusb`; OUT endpoint `0x02` |
| IF3 | Vendor HID `0xFF00`, 64 bytes | `hidapi`: commands, acknowledgements and key presses |

**Why the Linux driver hangs on a Mac:** the firmware ignores every command on IF3 until
it gets output report 3 = `[0x03, 0x01]` on IF0 ("event mode"). On Linux it is sent by
detaching IF0 from the kernel, which needs root on macOS. Here it is sent by opening IF0
in shared mode with IOKit, which needs no root, only the Input Monitoring permission.

Each key picture is one 102 × 102 BGR transfer of 31,744 bytes on IF1, about 18 ms.

## Made with AI

This project was written with **Claude Code**, Anthropic's AI coding assistant: the
driver, the service, the configurator, the MCP server, the installer and this README.
A person directed the work, decided what to build and tested every feature on a real
DisplayPad on macOS. Review the code as you would any other open-source project before
you rely on it.

## Credits

- USB protocol and image upload sequence:
  [oss-mountain-displaypad](https://github.com/AnnikenYT/oss-mountain-displaypad) by
  AnnikenToGo (MIT). Reimplemented in Python in `displaypad_mac/driver.py`.
- How the pad is switched on was first understood from
  [BaseCamp-Linux](https://github.com/ramisotti13-eng/BaseCamp-Linux) (consulted only,
  no code copied).
- Lottie animations: [rlottie](https://github.com/Samsung/rlottie) through
  [rlottie-python](https://github.com/laggykiller/rlottie-python) (LGPL 2.1).
- The macOS part (IOKit activation, claiming IF1 with libusb, the service, actions,
  screen brightness, configurator and MCP server) is new and was verified on the hardware.

Details and license texts: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

[MIT](LICENSE). Not affiliated with, endorsed by or supported by Mountain or 360 Service
Agency GmbH. Mountain and DisplayPad are trademarks of their owners.
