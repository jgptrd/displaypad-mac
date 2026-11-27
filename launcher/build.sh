#!/bin/bash
# Builds DisplayPad.app (the configurator window and the floating pad) from DisplayPad.swift.
#   launcher/build.sh OUTPUT.app PYTHON
# PYTHON is the service's Python (it draws the icon). Needs the Xcode Command Line Tools (swiftc):
#   xcode-select --install
# DISPLAYPAD_APP_ID changes the bundle id (tests); the service opens the app by that id.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?usage: build.sh OUTPUT.app PYTHON}"
PY="${2:?usage: build.sh OUTPUT.app PYTHON}"
APP_ID="${DISPLAYPAD_APP_ID:-com.displaypadmac.app}"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$HERE/../displaypad_mac/__init__.py")"

# (without the Command Line Tools, /usr/bin/swiftc only offers to install them)
xcode-select -p >/dev/null 2>&1 && command -v swiftc >/dev/null 2>&1 || { echo "swiftc not found"; exit 2; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
B="$TMP/DisplayPad.app/Contents"
mkdir -p "$B/MacOS" "$B/Resources"

MIN=12.0
ARCH="$(uname -m)"
# SWIFT_FLAGS: extra compiler flags (tests: -D DEBUG_HOOKS)
swiftc -O -swift-version 5 -suppress-warnings -target "$ARCH-apple-macos$MIN" ${SWIFT_FLAGS:-} \
  -o "$B/MacOS/DisplayPad" "$HERE/DisplayPad.swift" \
  -framework Cocoa -framework WebKit -framework Carbon -framework UserNotifications

cat > "$B/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>$APP_ID</string>
  <key>CFBundleName</key><string>DisplayPad</string>
  <key>CFBundleDisplayName</key><string>DisplayPad</string>
  <key>CFBundleExecutable</key><string>DisplayPad</string>
  <key>CFBundleIconFile</key><string>DisplayPad</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleLocalizations</key><array><string>en</string><string>es</string></array>
  <key>LSMinimumSystemVersion</key><string>$MIN</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticTermination</key><false/>
  <key>NSHumanReadableCopyright</key><string>DisplayPad for macOS — github.com/jgptrd/displaypad-mac</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
EOF

(cd "$HERE/.." && "$PY" -m displaypad_mac.appicon "$TMP/DisplayPad.iconset")
iconutil -c icns "$TMP/DisplayPad.iconset" -o "$B/Resources/DisplayPad.icns"
codesign --force --sign - "$TMP/DisplayPad.app" >/dev/null 2>&1 || true

rm -rf "$OUT"
ditto "$TMP/DisplayPad.app" "$OUT"
touch "$OUT"
