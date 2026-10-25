#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Linux ]]; then
    echo 'Build the Linux executable on Linux. Use wifi_request.spec on Windows.' >&2
    exit 1
fi
python_command="${PYTHON:-python3}"
if ! "$python_command" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit('Use Python 3.10 or newer.')
import tkinter, gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, AyatanaAppIndicator3
PY
then
    echo 'Install: sudo apt install python3-venv python3-tk python3-gi gir1.2-ayatanaappindicator3-0.1 fontconfig binutils' >&2
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    "$python_command" -m venv --system-site-packages .venv
fi
.venv/bin/python -m pip install -r requirements.txt
# Ubuntu splits Pillow's ImageTk into a separate package. The GI-visible venv
# may otherwise reuse that incomplete system Pillow; install a complete wheel locally.
if ! .venv/bin/python -c 'from PIL import ImageTk' >/dev/null 2>&1; then
    .venv/bin/python -m pip install --ignore-installed --only-binary=:all: Pillow
fi
.venv/bin/python -m PyInstaller --clean --noconfirm wifi_request_linux.spec
printf '\nLinux executable: %s/dist/wifi_request\n' "$PWD"
