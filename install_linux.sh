#!/usr/bin/env bash
# Install for this user; no sudo, shell-profile changes or automatic app launch.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x dist/wifi_request ]]; then
    echo 'Run bash build_linux.sh first.' >&2
    exit 1
fi
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/wifi-request"
bin_dir="$HOME/.local/bin"
applications="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_theme="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
icons="$icon_theme/512x512/apps"
legacy_icon="$icon_theme/256x256/apps/wifi-request.png"
mkdir -p -- "$app_dir" "$bin_dir" "$applications" "$icons"
install -m 755 dist/wifi_request "$app_dir/wifi_request"
install -m 644 icon/app.png "$icons/wifi-request.png"
if [[ -f "$legacy_icon" ]]; then
    rm -- "$legacy_icon"
fi
ln -sfn -- "$app_dir/wifi_request" "$bin_dir/wifi_request"
# Quote paths for the desktop Exec field (not a shell command).
python3 - "$app_dir/wifi_request" "$applications/wifi-request.desktop" <<'PY'
import sys
from pathlib import Path
from platform_linux import desktop_exec
source = Path('wifi-request.desktop').read_text()
source = source.replace('Exec=wifi_request', 'Exec=' + desktop_exec([sys.argv[1]]))
Path(sys.argv[2]).write_text(source)
PY
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications"
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$icon_theme"
elif command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "$icon_theme"
fi
printf 'Installed: %s/wifi_request\nOpen WiFi Request from the application menu.\n' "$app_dir"
