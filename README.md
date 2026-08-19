# Auto-Gmail-Creator

This repository contains an older Selenium browser-automation example. The Termux compatibility patch removes desktop-only driver downloading, fixes path and cleanup errors, and makes secrets environment-controlled. It does **not** add CAPTCHA bypasses, stealth automation, proxy rotation, referer randomization, or other anti-abuse evasion.

## Termux installation

Use a current Termux build, then run:

```bash
pkg update -y
pkg install -y tur-repo x11-repo python chromium

git clone https://github.com/varahta700-oss/Auto-Gmail-Creator.git
cd Auto-Gmail-Creator
bash setup_termux.sh
```

The setup script creates `.venv`, installs the minimal Python dependencies, and checks that `chromedriver` is available. The Chromium package is expected to provide a matching driver. If the driver is installed in a non-standard location, set it explicitly:

```bash
export CHROMEDRIVER=/absolute/path/to/chromedriver
export CHROME_BINARY="$(command -v chromium || command -v chromium-browser)"
```

Because a normal Termux shell usually has no graphical display, the application automatically selects Chromium's compatible legacy headless mode when `TERMUX_VERSION` is present and `DISPLAY` is unset. To select it explicitly, use:

```bash
export HEADLESS=1
. .venv/bin/activate
python app.py
```

For a configured Termux:X11 display, set `HEADLESS=0` and export `DISPLAY` as required by that environment.

## Configuration

The application reads runtime values from environment variables. No API key or proxy credential is stored in the repository. Supported settings include `AUTO_GENERATE_USERINFO`, `AUTO_GENERATE_NUMBER`, `WAIT_SECONDS`, `PAGE_LOAD_TIMEOUT`, `NAVIGATION_RETRIES`, `PAGE_LOAD_STRATEGY`, `REQUEST_MAX_TRY`, `USER_CSV`, `USERNAME_BASE`, `USERNAME_SUFFIX_LENGTH`, `CHROMEDRIVER`, `CHROME_BINARY`, and `HEADLESS`.

The Termux interface now shows a dashboard at startup, numbered registration steps, browser and driver detection, username-attempt progress, verification status, success/failure messages, elapsed time, and a final run summary. Each attempt is also written to `registration_results.csv`. A `completed` row means the program reached its final submission step and saved the local record to `Created.txt`; a `failed` row includes the exception type and a shortened diagnostic message. Passwords and SMS API responses are not printed in the dashboard.

For a slow or unstable mobile connection, Termux now defaults to Selenium's `none` page-load strategy, while desktop systems default to `eager`. Both use a 30-second page-load timeout, stop waiting for nonessential subresources, and retry timed-out navigations twice. You can tune these values locally:

```bash
export PAGE_LOAD_TIMEOUT=45
export NAVIGATION_RETRIES=3
export PAGE_LOAD_STRATEGY=eager
```

When automatic user information is enabled, the program asks once:

```text
What should the Gmail username start from? Example: misa.amane (leave blank to use first.last):
```

Entering `misa.amane` generates usernames in the form `misa.amanex7k2q`, with a new lowercase-alphanumeric suffix for each generated username. The default suffix length is five characters. Set `USERNAME_SUFFIX_LENGTH` to another value from 1 to 32 if needed. For non-interactive execution, set `USERNAME_BASE` before starting the program:

```bash
export USERNAME_BASE='misa.amane'
export USERNAME_SUFFIX_LENGTH=5
python app.py
```

If a verification provider is required by the site flow, provide a key only in your local shell environment, for example:

```bash
export SMS_ACTIVATE_API_KEY='your-own-key'
export SMS_ACTIVATE_COUNTRY='175'
```

Do not commit secrets, private proxy credentials, or generated account data. The lowercase repository file is `user.csv`; the code now resolves it relative to the project directory and also accepts an alternate path through `USER_CSV`.

## What was fixed

The application now imports standard Selenium instead of Selenium Wire, so the `pkg_resources` import failure is avoided. It no longer calls `webdriver-manager`, which was attempting to download an unavailable `None-arm64` driver on Termux. It first uses `CHROMEDRIVER` or `chromedriver` on `PATH`, detects `chromium`, `chromium-browser`, or `google-chrome`, uses Selenium Manager only as a desktop fallback, and reports a clear error when Termux has no compatible browser or driver. Browser navigation now uses an explicit page-load timeout, Selenium's modern page-load strategy, retry logging, and `window.stop()` after a timeout so a slow third-party resource cannot block the whole run for two minutes.

The patch also fixes the uninitialized `driver` cleanup error, the unconditional `user_info_file.close()` call, case-sensitive `User.csv` path handling, relative data paths, unbounded SMS-code polling, missing HTTP timeouts, and the committed SMS/proxy credentials found in the original source.

## Troubleshooting

Check the browser and driver independently:

```bash
CHROME_BIN="$(command -v chromium || command -v chromium-browser)"
"$CHROME_BIN" --version
command -v chromedriver
chromedriver --version
```

The browser and driver major versions must match. If `command -v chromedriver` returns nothing, update the Termux repositories and reinstall Chromium before running the Python program. Do not use a desktop x86 or x86_64 driver on an ARM64 Android installation.

If Python reports a missing module, activate the project environment and reinstall only the declared dependencies:

```bash
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The Google account-creation flow and selectors are controlled by Google and can change without notice. A successful driver launch does not guarantee that an external website will permit or complete an automated flow. Use the project only where you have authorization and comply with the service's terms and applicable law.
