#!/bin/zsh
# Stops and removes the service. With --all it also deletes your configuration and icons.
set -euo pipefail
LABEL="com.displaypadmac.agent"
APP="$HOME/Library/Application Support/DisplayPadMac"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
pkill -x DisplayPad 2>/dev/null || true  # the app (configurator window, floating pad)
rm -rf "/Applications/DisplayPad.app" "$HOME/Applications/DisplayPad.app"
echo "Service stopped and removed from login items."

if [[ "${1:-}" == "--all" || "${1:-}" == "--todo" ]]; then
  rm -rf "$APP"
  echo "Deleted: $APP"
else
  echo "Your configuration is still in: $APP (use --all to delete it)"
fi
