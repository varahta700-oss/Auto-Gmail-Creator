import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import TimeoutException

import app


class TermuxCompatibilityTests(unittest.TestCase):
    def test_import_uses_repository_relative_paths(self):
        self.assertEqual(app.BASE_DIR, Path(__file__).resolve().parent)
        self.assertEqual(app.USER_CSV, app.BASE_DIR / "user.csv")

    def test_termux_is_detected_from_prefix(self):
        with patch.dict(os.environ, {"TERMUX_VERSION": "0", "PREFIX": "/data/data/com.termux/files/usr"}, clear=False):
            self.assertTrue(app._is_termux())

    def test_chromium_browser_name_is_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            browser = Path(temp_dir) / "chromium-browser"
            browser.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            browser.chmod(browser.stat().st_mode | stat.S_IXUSR)
            with patch.dict(os.environ, {"CHROME_BINARY": ""}, clear=False), patch(
                "app.shutil.which", side_effect=[None, str(browser), None]
            ):
                self.assertEqual(app._find_chrome_binary(), str(browser))

    def test_explicit_driver_path_is_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            driver = Path(temp_dir) / "chromedriver"
            driver.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            driver.chmod(driver.stat().st_mode | stat.S_IXUSR)
            with patch.dict(os.environ, {"CHROMEDRIVER": str(driver)}, clear=False):
                self.assertEqual(app._find_chromedriver(), str(driver))

    def test_termux_uses_explicit_driver_and_legacy_headless(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            driver = Path(temp_dir) / "chromedriver"
            driver.write_text("#!/bin/sh\\nexit 0\\n", encoding="utf-8")
            driver.chmod(driver.stat().st_mode | stat.S_IXUSR)
            env = {
                "TERMUX_VERSION": "0",
                "PREFIX": "/data/data/com.termux/files/usr",
                "CHROMEDRIVER": str(driver),
                "DISPLAY": "",
                "HEADLESS": "",
            }
            mock_driver = MagicMock()
            with patch.dict(os.environ, env, clear=False), patch("app.webdriver.Chrome", return_value=mock_driver) as chrome:
                self.assertIs(app.setDriver(), mock_driver)
                options = chrome.call_args.kwargs["options"]
                service = chrome.call_args.kwargs["service"]
                self.assertEqual(service.path, str(driver))
                self.assertTrue(any(argument.startswith("--headless") for argument in options.arguments))
                self.assertIn("--headless=new", options.arguments)
                self.assertEqual(options.page_load_strategy, app.PAGE_LOAD_STRATEGY)
                mock_driver.set_page_load_timeout.assert_called_once_with(app.PAGE_LOAD_TIMEOUT)
                mock_driver.set_script_timeout.assert_called_once_with(app.PAGE_LOAD_TIMEOUT)

    def test_navigation_retries_after_timeout_with_fresh_session(self):
        driver = MagicMock()
        driver.current_url = "https://example.invalid/"
        driver.get.side_effect = [TimeoutException("slow page"), None]
        with patch("app.setDriver", return_value=driver) as restart:
            returned = app.navigate(driver, "https://example.invalid", retries=1)
        self.assertIs(returned, driver)
        self.assertEqual(driver.get.call_count, 2)
        driver.execute_script.assert_called_once_with("window.stop();")
        restart.assert_called_once_with()

    def test_navigation_rejects_about_blank(self):
        driver = MagicMock()
        driver.current_url = "about:blank"
        with patch("app.setDriver", return_value=driver):
            with self.assertRaisesRegex(RuntimeError, "about:blank"):
                app.navigate(driver, "https://example.invalid", retries=0)

    def test_termux_without_driver_has_actionable_error(self):
        env = {
            "TERMUX_VERSION": "0",
            "PREFIX": "/data/data/com.termux/files/usr",
            "CHROMEDRIVER": "/does/not/exist",
            "DISPLAY": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Android/ARM64-compatible driver"):
                app.setDriver()

    def test_username_base_is_normalized(self):
        self.assertEqual(app.normalize_username_base(" Misa Amane@example.com "), "misa.amane")
        self.assertEqual(app.normalize_username_base("misa..amane!!!"), "misa.amane")

    def test_username_has_requested_base_and_random_suffix(self):
        first = app.generate_username("misa.amane", suffix_length=8)
        second = app.generate_username("misa.amane", suffix_length=8)
        self.assertTrue(first.startswith("misa.amane"))
        self.assertTrue(second.startswith("misa.amane"))
        self.assertEqual(len(first), len("misa.amane") + 8)
        self.assertRegex(first[len("misa.amane"):], r"^[a-z0-9]{8}$")
        self.assertNotEqual(first, second)

    def test_blank_prompt_falls_back_to_default(self):
        with patch("builtins.input", return_value=""):
            self.assertEqual(app.prompt_username_base(), "")

    def test_failure_diagnostics_create_local_artifacts(self):
        class FakeDriver:
            current_url = "https://accounts.google.com/signup"
            title = "Signup"
            page_source = "<html><body>example</body></html>"

            def save_screenshot(self, path):
                Path(path).write_bytes(b"PNG")

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(app, "DIAGNOSTICS_DIR", Path(temp_dir)):
                prefix = app.save_failure_diagnostics(FakeDriver(), 1, "test failure")
            self.assertIsNotNone(prefix)
            self.assertTrue(Path(f"{prefix}.png").exists())
            self.assertTrue(Path(f"{prefix}.html").exists())

    def test_result_logging_records_status_without_password(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "registration_results.csv"
            results = []
            with patch.object(app, "RESULT_LOG", log_path):
                app.record_result(results, 1, "misa.amanex7k2q", "failed", "TimeoutException: page did not load")
            self.assertEqual(results[0]["status"], "failed")
            self.assertNotIn("password", log_path.read_text(encoding="utf-8").lower())
            self.assertIn("misa.amanex7k2q", log_path.read_text(encoding="utf-8"))

    def test_legacy_dependency_and_secret_patterns_are_gone(self):
        source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        requirements = Path(__file__).with_name("requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("seleniumwire", source)
        self.assertNotIn("webdriver_manager", source)
        self.assertNotIn("FreeProxy", source)
        self.assertNotIn("from fake_useragent", source)
        self.assertNotIn("14ab1e7131541", source)
        self.assertNotIn("selenium_wire", requirements)
        self.assertNotIn("webdriver_manager", requirements)


if __name__ == "__main__":
    unittest.main()
