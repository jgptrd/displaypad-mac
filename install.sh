#!/bin/zsh
# Installs DisplayPadMac as a per-user service that starts at login.
# Run it again to update: your config.json is kept.
set -euo pipefail

SRC="${0:A:h}"
APP="$HOME/Library/Application Support/DisplayPadMac"
LABEL="com.displaypadmac.agent"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/DisplayPadMac.log"

PY=""
for c in python3.14 python3.15 python3.13 python3.12 python3.11; do
  if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
done
[[ -n "$PY" ]] || { echo "Python 3.11 or newer is needed: brew install python@3.14"; exit 1; }

if [[ ! -f /opt/homebrew/lib/libusb-1.0.dylib && ! -f /usr/local/lib/libusb-1.0.dylib ]]; then
  echo "Installing libusb with Homebrew..."
  brew install libusb
fi

echo "Copying files to: $APP"
mkdir -p "$APP/icons" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
rsync -a --delete --exclude '__pycache__' "$SRC/displaypad_mac/" "$APP/displaypad_mac/"
cp "$SRC/requirements.txt" "$SRC/config.example.json" "$SRC/README.md" "$SRC/LICENSE" "$APP/" 2>/dev/null || true
if [[ ! -f "$APP/config.json" ]]; then
  cp "$SRC/config.example.json" "$APP/config.json"
  echo "Created the starting configuration: $APP/config.json"
else
  echo "Keeping your configuration: $APP/config.json"
fi

echo "Setting up Python ($PY)..."
[[ -x "$APP/.venv/bin/python" ]] || "$PY" -m venv "$APP/.venv"
"$APP/.venv/bin/python" -m pip install -q --upgrade pip
"$APP/.venv/bin/python" -m pip install -q -r "$APP/requirements.txt"

# Bridge for AI apps that start a local MCP server (Claude Desktop, Claude Code...).
# It forwards to the running service and reads the access key itself.
cat > "$APP/displaypad-mcp" <<EOF
#!/bin/zsh
# MCP server for AI assistants (stdio). Turn it on in DisplayPad > Settings > AI assistants.
export PYTHONPATH="$APP"
exec "$APP/.venv/bin/python" -m displaypad_mac mcp "\$@"
EOF
chmod 755 "$APP/displaypad-mcp"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$APP/.venv/bin/python</string>
    <string>-m</string><string>displaypad_mac</string>
    <string>run</string>
    <string>--config</string><string>$APP/config.json</string>
  </array>
  <key>WorkingDirectory</key><string>$APP</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$APP</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF

echo "Creating the DisplayPad app (the configurator's window and the floating pad)..."
# In /Applications it shows up in Finder, Launchpad and Spotlight. It is built here from
# launcher/DisplayPad.swift; without the Xcode Command Line Tools a simpler one opens the
# configurator in the browser, and the floating pad is not available.
if [[ -w /Applications ]]; then LAUNCHER="/Applications/DisplayPad.app"
else LAUNCHER="$HOME/Applications/DisplayPad.app"; mkdir -p "$HOME/Applications"; fi
TMPI="$(mktemp -d)"
NATIVE=1
if ! "$SRC/launcher/build.sh" "$TMPI/DisplayPad.app" "$APP/.venv/bin/python" >"$TMPI/build.log" 2>&1; then
  NATIVE=0
  echo "  The app could not be built: it needs the Xcode Command Line Tools (xcode-select --install)."
  echo "  For now the DisplayPad app opens the configurator in your browser, without the floating pad."
  tail -3 "$TMPI/build.log" | sed 's/^/    /'
fi
pkill -x DisplayPad 2>/dev/null || true  # the running one, before it is replaced
rm -rf "$LAUNCHER" "$HOME/Applications/DisplayPad.app"
if (( NATIVE )); then
  ditto "$TMPI/DisplayPad.app" "$LAUNCHER"
else
  osacompile -o "$LAUNCHER" "$SRC/launcher/DisplayPad.applescript"
  "$APP/.venv/bin/python" -m displaypad_mac.appicon "$TMPI/DisplayPad.iconset"
  iconutil -c icns "$TMPI/DisplayPad.iconset" -o "$LAUNCHER/Contents/Resources/applet.icns"
  rm -rf "$LAUNCHER/Contents/Resources/Assets.car"
  codesign --force --sign - "$LAUNCHER" >/dev/null 2>&1 || true
fi
rm -rf "$TMPI"
touch "$LAUNCHER"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$LAUNCHER" 2>/dev/null || true
mdimport "$LAUNCHER" 2>/dev/null || true

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
for i in {1..20}; do  # bootout is asynchronous: wait until the old service is gone
  launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || break
  sleep 0.5
done
for i in {1..5}; do
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null && break
  [[ $i == 5 ]] && { echo "Could not register the service with launchctl"; exit 1; }
  sleep 1
done

PYAPP="$("$APP/.venv/bin/python" -c 'import sys,os;print(os.path.join(sys.base_prefix,"Resources","Python.app"))')"
cat <<EOF

✅ DisplayPadMac is installed and running.

   Configurator:   open the "DisplayPad" app ($LAUNCHER)
                   or press the ⚙️ Configure key on the pad
   Floating pad:   ⌘ + middle click anywhere (change it in the app, Settings > Floating pad)
   Configuration:  $APP/config.json   (reloads by itself when saved)
   Log:            $LOG
   AI assistants:  turn them on in the app, Settings > AI assistants

macOS asks for two permissions for "Python" (it can take a few seconds):
  • Input Monitoring  -> needed to talk to the DisplayPad
  • Accessibility     -> needed for shortcuts, typed text, media keys and
                         the floating pad's mouse shortcut
If no prompt appears, add it by hand in System Settings >
Privacy & Security > (Input Monitoring / Accessibility) > "+":
   $PYAPP
EOF
