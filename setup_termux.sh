#!/data/data/com.termux/files/usr/bin/bash
set -eu

if [ "$(uname -o 2>/dev/null || true)" != "Android" ] && [ -z "${TERMUX_VERSION:-}" ]; then
    echo "This helper is intended for Termux on Android." >&2
    exit 1
fi

pkg update -y
pkg install -y tur-repo x11-repo python chromium

python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if ! command -v chromedriver >/dev/null 2>&1; then
    echo
    echo "Chromium is installed, but chromedriver is not on PATH."
    echo "Update Termux packages and verify the Chromium package includes its matching driver."
    echo "Then run: command -v chromedriver"
    echo "If it exists elsewhere, export CHROMEDRIVER=/absolute/path/to/chromedriver"
    exit 2
fi

chmod +x "$(command -v chromedriver)" 2>/dev/null || true
printf '\nReady. Chromium: %s\nChromeDriver: %s\n' "$(command -v chromium || command -v chromium-browser)" "$(command -v chromedriver)"
printf 'Run with: . .venv/bin/activate && python app.py\n'
