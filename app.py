# from selenium import webdriver
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import random
import datetime
import requests
import csv
import string
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Runtime settings can be overridden with environment variables. Secrets must
# never be committed to the repository.
AUTO_GENERATE_USERINFO = os.getenv("AUTO_GENERATE_USERINFO", "1").lower() in {"1", "true", "yes"}
AUTO_GENERATE_NUMBER = int(os.getenv("AUTO_GENERATE_NUMBER", "10"))
WAIT = float(os.getenv("WAIT_SECONDS", "4"))
PAGE_LOAD_TIMEOUT = float(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
NAVIGATION_RETRIES = int(os.getenv("NAVIGATION_RETRIES", "2"))
_DEFAULT_PAGE_LOAD_STRATEGY = "none" if (
    os.getenv("TERMUX_VERSION") or "com.termux" in os.getenv("PREFIX", "")
) else "eager"
PAGE_LOAD_STRATEGY = os.getenv("PAGE_LOAD_STRATEGY", _DEFAULT_PAGE_LOAD_STRATEGY).strip().lower()
if PAGE_LOAD_STRATEGY not in {"normal", "eager", "none"}:
    PAGE_LOAD_STRATEGY = "eager"
REQUEST_MAX_TRY = int(os.getenv("REQUEST_MAX_TRY", "10"))
USER_CSV = Path(os.getenv("USER_CSV", str(BASE_DIR / "user.csv")))
USERNAME_BASE = os.getenv("USERNAME_BASE", "").strip()
USERNAME_SUFFIX_LENGTH = int(os.getenv("USERNAME_SUFFIX_LENGTH", "5"))
SMS_ACTIVATE_API_KEY = os.getenv("SMS_ACTIVATE_API_KEY", "").strip()
SMS_ACTIVATE_COUNTRY = os.getenv("SMS_ACTIVATE_COUNTRY", "175").strip()
sms_activate_url = "https://sms-activate.org/stubs/handler_api.php"

# Referer randomization, proxy rotation, and stealth settings were removed.
# They are unreliable on Termux and can be used to evade anti-abuse controls.
INCLUDE_REFER_URL = False

SELECTORS = {
    "create_account":[
        "//button[@class='VfPpkd-LgbsSe VfPpkd-LgbsSe-OWXEXe-dgl2Hf ksBjEc lKxP2d LQeN7 FliLIb uRo0Xe TrZEUc Xf9GD']",
        "//*[@class='JnOM6e TrZEUc kTeh9 KXbQ4b']"
        ],
    'for_my_personal_use':[
        "//span[@class='VfPpkd-StrnGf-rymPhb-b9t22c']",
        ],
    "first_name":"//*[@name='firstName']",
    "last_name":"//*[@name='lastName']",
    "username":"//*[@name='Username']",
    "password":"//*[@name='Passwd']",
    "confirm_password":"//*[@name='PasswdAgain']",
    "next":[
            "//button[@class='VfPpkd-LgbsSe VfPpkd-LgbsSe-OWXEXe-k8QpJ VfPpkd-LgbsSe-OWXEXe-dgl2Hf nCP5yc AjY5Oe DuMIQc LQeN7 qIypjc TrZEUc lw1w4b']",
            "//button[contains(text(),'Next')]",
            "//button[contains(text(),'I agree')]"
    ],
    "phone_number":"//*[@id='phoneNumberId']",
    "code":'//input[@name="code"]',
    "acc_phone_number":'//input[@id="phoneNumberId"]',
    "acc_day":'//input[@name="day"]',
    "acc_month":'//select[@id="month"]',
    "acc_year":'//input[@name="year"]',
    "acc_gender":'//select[@id="gender"]',
    "username_warning":'//*[@class="jibhHc"]',
    "username_select":'//*[@aria-posinset="3"]'
}
# Repository data is resolved relative to BASE_DIR inside main().

def generatePassword():
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + string.punctuation
    size = random.randint(8, 12)
    return ''.join(random.choice(chars) for x in range(size))


def normalize_username_base(value):
    """Return a Gmail-style local-part base using letters, digits, and dots."""
    value = value.strip().lower().split("@", 1)[0]
    value = "".join(char if char.isalnum() or char == "." else "." for char in value)
    value = ".".join(part for part in value.split(".") if part)
    return value.strip(".")


def generate_username(base, suffix_length=None):
    """Append a random lowercase-alphanumeric suffix to a normalized base."""
    normalized = normalize_username_base(base)
    if not normalized:
        raise ValueError("Username base must contain at least one letter or digit.")
    length = USERNAME_SUFFIX_LENGTH if suffix_length is None else int(suffix_length)
    if length < 1 or length > 32:
        raise ValueError("Username suffix length must be between 1 and 32.")
    suffix_chars = string.ascii_lowercase + string.digits
    suffix = "".join(random.choice(suffix_chars) for _ in range(length))
    return normalized + suffix


def prompt_username_base():
    """Read a base once, allowing non-interactive use through USERNAME_BASE."""
    if USERNAME_BASE:
        return normalize_username_base(USERNAME_BASE)
    try:
        entered = input(
            "What should the Gmail username start from? "
            "Example: misa.amane (leave blank to use first.last): "
        )
    except EOFError:
        entered = ""
    return normalize_username_base(entered)

def getRandomeUserAgent():
    UAGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36 Edg/106.0.1370.52',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 YaBrowser/21.8.1.468 Yowser/2.5 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:105.0) Gecko/20100101 Firefox/105.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64; rv:105.0) Gecko/20100101 Firefox/105.0',
        'Mozilla/5.0 (X11; CrOS x86_64 14440.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4807.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14467.0.2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4838.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.7.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.13 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14455.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4827.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.11.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.17 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14436.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4803.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14475.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.3.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.9 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14471.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14388.37.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.9 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14409.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4829.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14395.0.2021) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4765.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.8.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.14 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14484.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14450.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4817.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14473.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14324.72.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.91 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14454.0.2022) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4824.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14453.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4816.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14447.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4815.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14477.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14476.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4840.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.8.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.9 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.67.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.67.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.69.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.82 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.25.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.22 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.89.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.133 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.57.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.64 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.89.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.133 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.84.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.93 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.59.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.91.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.55 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.23.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.20 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.36.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.36 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.41.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.26 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.11.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.6 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.67.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14685.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.4992.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.69.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.82 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14682.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.16 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.9.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.5 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14574.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4937.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14388.52.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14716.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5002.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14268.81.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14469.41.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.48 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14388.61.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.37.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.37 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.51.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.32 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.89.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.133 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.92.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.56 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.43.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.54 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14505.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4870.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.16.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.25 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.28.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.44 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14543.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4918.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.11.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.6 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.89.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.133 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14588.31.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.19 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14526.6.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.13 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14658.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.4975.0 Safari/537.36',
        'Mozilla/5.0 (X11; CrOS x86_64 14695.25.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5002.0 Safari/537.36'
    ]
    agent = random.choice(UAGENTS)
    return agent

# This method is for chrome driver initialization. You can customize if you want.
def _is_termux():
    return bool(os.getenv("TERMUX_VERSION")) or "com.termux" in os.getenv("PREFIX", "")


def _find_chromedriver():
    configured = os.getenv("CHROMEDRIVER", "").strip()
    candidate = configured or shutil.which("chromedriver")
    if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _find_chrome_binary():
    configured = os.getenv("CHROME_BINARY", "").strip()
    if configured and os.path.isfile(configured) and os.access(configured, os.X_OK):
        return configured
    for command in ("chromium", "chromium-browser", "google-chrome"):
        candidate = shutil.which(command)
        if candidate:
            return candidate
    return None


def navigate(driver, url, retries=None):
    """Navigate without waiting forever for third-party resources.

    Chromium can keep a page loading because of analytics, blocked resources,
    or a slow mobile connection. Termux defaults to Selenium's `none` strategy,
    while desktop systems default to `eager`; explicit element waits below still
    control when the workflow proceeds.
    """
    attempts = NAVIGATION_RETRIES if retries is None else max(0, int(retries))
    last_error = None
    for attempt in range(attempts + 1):
        try:
            print(f"################ Navigate ({attempt + 1}/{attempts + 1}): {url} ################")
            driver.get(url)
            return
        except TimeoutException as error:
            last_error = error
            print(f"Navigation timed out after {PAGE_LOAD_TIMEOUT:g}s: {url}")
            try:
                driver.execute_script("window.stop();")
            except WebDriverException:
                pass
            if attempt < attempts:
                time.sleep(1)
    raise RuntimeError(f"Unable to load {url} after {attempts + 1} attempt(s): {last_error}") from last_error


def setDriver():
    """Start Chromium using a driver supplied by the user or on PATH.

    webdriver-manager downloads desktop binaries and cannot reliably resolve
    the Android/ARM64 combination used by Termux, so it is deliberately not
    used here.
    """
    options = ChromeOptions()
    options.page_load_strategy = PAGE_LOAD_STRATEGY
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")

    chrome_binary = _find_chrome_binary()
    if chrome_binary:
        options.binary_location = chrome_binary
    elif _is_termux():
        raise RuntimeError(
            "No Chromium executable was found. Termux may name it "
            "chromium-browser; install the Chromium package or set "
            "CHROME_BINARY=/absolute/path/to/chromium-browser."
        )

    # Termux normally has no DISPLAY. Its compatible mode is legacy
    # --headless; callers can set HEADLESS=0 under a configured X11 display.
    headless = os.getenv("HEADLESS", "").lower() in {"1", "true", "yes"}
    if not headless and _is_termux() and not os.getenv("DISPLAY"):
        headless = True
    if headless:
        options.add_argument("--headless")

    driver_path = _find_chromedriver()
    if driver_path:
        driver = webdriver.Chrome(service=Service(driver_path), options=options)
    elif _is_termux():
        raise RuntimeError(
            "No executable chromedriver was found. On Termux, install an "
            "Android/ARM64-compatible driver and set CHROMEDRIVER=/path/to/chromedriver "
            "or put it on PATH; webdriver-manager cannot supply this binary."
        )
    else:
        # On regular desktop Linux, Selenium Manager may resolve a matching driver.
        driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.set_script_timeout(PAGE_LOAD_TIMEOUT)
    return driver

def main():
    user_number = 0
    i = 0

    if AUTO_GENERATE_USERINFO:
        user_number = AUTO_GENERATE_NUMBER
        username_base = prompt_username_base()
        print('################ Open First_Name_DB.csv ################')
        try:
            with open(BASE_DIR / "data" / "First_Name_DB.csv", newline="", encoding="utf-8") as first_name_file:
                first_names = list(csv.reader(first_name_file))
        except:
            print('################ Please check if First_Name_DB.csv exists ################')
            quit()

        print('################ Open Last_Name_DB.csv ################')
        try:
            with open(BASE_DIR / "data" / "Last_Name_DB.csv", newline="", encoding="utf-8") as last_name_file:
                last_names = list(csv.reader(last_name_file))
        except:
            print('################ Please check if Last_Name_DB.csv exists ################')
            quit()
    else:
        print('################ Open User.csv ################')
        try:
            with open(USER_CSV, newline="", encoding="utf-8") as user_info_file:
                user_infos = list(csv.reader(user_info_file))
            user_number = len(user_infos)
        except:
            print('################ Please check if User.csv exists ################')
            quit()

    while True:
        driver = None
        try:
            # Check if the count reaches the configured maximum users.

            if i >= user_number:
                break

            i = i + 1
            print('################ User:', i,' ################')
            if AUTO_GENERATE_USERINFO:
                first_name = random.choice(first_names)[0]
                last_name = random.choice(last_names)[0]
                password = generatePassword()
                birthday = str(random.randint(1,12)) + "/" + str(random.randint(1,28)) + "/" +  str(random.randint(1980,1999))
                user_name_manual = ""
                print(first_name + "\t" + last_name + "\t" + password + '\t' + birthday)
            else:
                row = user_infos[i]
                if "Firstname" == row[0]:
                    continue

                first_name = row[0]
                last_name = row[1]
                password = row[2]
                birthday = row[3]
                print(first_name + "\t" + last_name + "\t" + password + '\t' + birthday)
            try:
                user_name_manual = row[4]
            except:
                user_name_manual = ""

            print('################ Initialize Chrome Driver ################')
            driver = setDriver()

            if INCLUDE_REFER_URL:
                raise RuntimeError("Referer randomization is disabled for safe and predictable operation.")

            # 4 ways to go to account creation page.
            random_int = random.randint(1,4)
            if random_int ==  1:

                print('################ Creat a google account article ################')
                navigate(driver, 'https://support.google.com/accounts/answer/27441?hl=en')
                WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH,'//*[@id="hcfe-content"]/section/div/div[1]/article/section/div/div[1]/div/div[2]/a[1]'))).click()
                time.sleep(WAIT)
            elif random_int == 2:
                print('################ Go to account page ################')
                navigate(driver, "https://accounts.google.com")

                time.sleep(WAIT)

                print('################ Click "Create account" ################')
                for selector in SELECTORS["create_account"]:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass
                print('################ Click "For my personal use" ################')
                for selector in SELECTORS["for_my_personal_use"]:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass

            elif random_int == 3:
                navigate(driver, 'https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp')
                time.sleep(WAIT)

            elif random_int == 4:
                navigate(driver, 'https://support.google.com/mail/answer/56256?hl=en')
                WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH,'//*[@id="hcfe-content"]/section/div/div[1]/article/section/div/div[1]/div/p[1]/a'))).click()
                time.sleep(WAIT)

            username_try = 0

            # if the username exists, it retries REQUEST_MAX_TRY times.
            while username_try < REQUEST_MAX_TRY:
                time.sleep(WAIT*2)

                print('################ 1st step of Creation Wizard. ################')


                print("################ Generate User Try: ", username_try+1, " ################")
                # set the first name.
                print('################ First Name ################')
                first_name_tag = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['first_name'])))
                first_name_tag.clear()
                time.sleep(WAIT/2)
                print(first_name)
                first_name_tag.send_keys(first_name)

                # set the surname.
                print('################ Last Name ################')
                last_name_tag = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['last_name'])))
                last_name_tag.clear()
                last_name_tag.send_keys(last_name)

                #click next button
                print('################ "Next" ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass
                time.sleep(WAIT*2)

                print('################ 2st step of Creation Wizard. ################')
                print('################ Birthday & Gender ################')
                # Date
                WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_day']))).send_keys(birthday.split('/')[1])

                # Month
                select_acc_month = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_month'])))

                acc_month = Select(select_acc_month)
                acc_month.select_by_value(birthday.split('/')[0])

                # Year
                WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_year']))).send_keys(birthday.split('/')[2])

                select_acc_gender = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_gender'])))

                # Gender
                acc_gender = Select(select_acc_gender)
                acc_gender.select_by_value('1')

               #click next button
                print('################ Click "Next" Buton ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass
                time.sleep(WAIT*2)

                # set username
                print('################ Set User Name ################')
                if user_name_manual == "":
                    default_base = username_base or (first_name + "." + last_name)
                    user_name = generate_username(default_base)
                else:
                    user_name = normalize_username_base(user_name_manual)
                try:
                    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['username_select']))).click()
                except:
                    pass
                try:
                    user_name_tag = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['username'])))
                    user_name_tag.clear()
                    print(user_name)
                    time.sleep(WAIT/2)
                    user_name_tag.send_keys(user_name)
                # time.sleep(WAIT*1000)
                except:
                    pass

                #click next button
                print('################ Click "Next" Buton ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass
                time.sleep(WAIT*2)
                print('################ Check Username Validation ################')
                try:
                    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['username_warning'])))
                    user_name_manual = ""
                    print("Invalid")
                    username_try = username_try + 1
                    continue
                except:
                    print("Valid")
                    pass

                # set password
                print('################ Set Password ################')
                passwd_tag =WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['password'])))
                passwd_tag.clear()
                passwd_tag.send_keys(password)

                print('################ Set Confirm Password ################')
                confirmwd_tag = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['confirm_password'])))
                confirmwd_tag.clear()
                confirmwd_tag.send_keys(password)

                #click next button
                print('################ Click "Next" Buton ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass
                time.sleep(WAIT*2)

                print('################ Check Phone Verification ################')
                without_verification = False
                try:
                    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_day'])))
                    without_verification = True
                    print("No. It doesn't require.")
                    break
                except:
                    print("Yes. It requires")
                    pass
                print('################ Input Phone Number ################')
                try:
                    phone_number_input = WebDriverWait(driver, WAIT*3).until(EC.presence_of_element_located((By.XPATH, SELECTORS['phone_number'])))
                    time.sleep(WAIT)
                    break
                except:
                    username_try = username_try + 1
            number = ""
            activationId = ""
            count = 0
            if without_verification == False:
                print('################ Get Phone Number from SMS_Activate ################')
                if not SMS_ACTIVATE_API_KEY:
                    raise RuntimeError(
                        "SMS verification is required, but SMS_ACTIVATE_API_KEY is not set. "
                        "Export your own key before running this step."
                    )
                phone_request_params = {
                    "api_key": SMS_ACTIVATE_API_KEY,
                    "action": "getNumber",
                    "country": SMS_ACTIVATE_COUNTRY,
                    "service": "go",
                }
                while count < REQUEST_MAX_TRY:
                    res = requests.get(url=sms_activate_url, params=phone_request_params, timeout=30)
                    res.raise_for_status()
                    data = res.text
                    print(data)
                    if "ACCESS_NUMBER" in data:
                        activationId = data.split(':')[1]
                        number = data.split(':')[2]

                        number = '+'+ number
                        print(number)
                        break
                    if "NO_BALANCE" in data:
                        raise RuntimeError("SMS provider balance is insufficient.")
                    count = count+1
                    time.sleep(WAIT)
                if number == '':
                    print("################ Cannot get phone number: ", REQUEST_MAX_TRY, " times retrial. ################")
                    raise RuntimeError("Go to next account.")

                phone_number_input.send_keys(number)

                #click next button
                print('################ Click "Next" Buton ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass

                print('################ Get SMS Code from SMS_Activate ################')
                time.sleep(WAIT)

                count_status = 0
                code = ''
                while count_status < REQUEST_MAX_TRY:
                    status_param = {
                        "api_key": SMS_ACTIVATE_API_KEY,
                        "action": "getStatus",
                        "id": activationId,
                    }
                    print(status_param)
                    res_code = requests.get(url=sms_activate_url, params=status_param, timeout=30)
                    res_code.raise_for_status()
                    data_code = res_code.text
                    print(data_code)
                    if "STATUS_OK" in data_code:
                        code = data_code.split(':')[1]
                        break

                    count_status = count_status + 1
                    time.sleep(WAIT*5)

                if code == '':
                    print('Cannot receive code from sms_activate: ',REQUEST_MAX_TRY, " times retrial")
                    raise RuntimeError("Go to next account.")

                print('################ Verify Phone Code ################')
                WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['code']))).send_keys(code)

                #click next button
                print('################ Click "Verify" Buton ################')
                for selector in SELECTORS['next']:
                    try:
                        WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                        break
                    except:
                        pass

            time.sleep(WAIT*2)
            print('################ Clear Account Phone Number ################')
            # WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_phone_number']))).clear()

            # print('################ Account Birthday ################')
            # # Date
            # WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_day']))).send_keys(birthday.split('/')[1])

            # # Month
            # select_acc_month = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_month'])))

            # acc_month = Select(select_acc_month)
            # acc_month.select_by_value(birthday.split('/')[0])

            # # Year
            # WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_year']))).send_keys(birthday.split('/')[2])

            # select_acc_gender = WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, SELECTORS['acc_gender'])))

            # # Gender
            # acc_gender = Select(select_acc_gender)
            # acc_gender.select_by_value('1')

            print('################ Click "Next" Buton ################')
            for selector in SELECTORS['next']:
                try:
                    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                    break
                except:
                    pass
            print('################ Click "I agree" Buton ################')
            time.sleep(WAIT)

            # Scroll to click "I agree"
            driver.execute_script("window.scrollTo(0, 800)")
            time.sleep(WAIT)
            for selector in SELECTORS['next']:
                try:
                    WebDriverWait(driver, WAIT).until(EC.presence_of_element_located((By.XPATH, selector))).click()
                    break
                except:
                    pass
            time.sleep(WAIT*3)
            print('################ Save to Created.txt ################')
            with open(BASE_DIR / "Created.txt", "a", encoding="utf-8") as created_file:
                created_file.write(user_name + "\t" + password + "\t" + birthday + "\t" + number + "\n")

            driver.quit()
            driver = None
        except Exception as e:
            print(e)
            if driver is not None:
                driver.quit()

if __name__ == "__main__":
    main()