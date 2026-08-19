import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class TermuxCompatibilityTests(unittest.TestCase):
    def test_import_uses_repository_relative_paths(self):
        self.assertEqual(app.BASE_DIR, Path(__file__).resolve().parent)
        self.assertEqual(app.USER_CSV, app.BASE_DIR / "user.csv")

    def test_termux_is_detected_from_prefix(self):
        with patch.dict(os.environ, {"TERMUX_VERSION": "0", "PREFIX": "/data/data/com.termux/files/usr"}, clear=False):
            self.assertTrue(app._is_termux())

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
            with patch.dict(os.environ, env, clear=False), patch("app.webdriver.Chrome", return_value="driver") as chrome:
                self.assertEqual(app.setDriver(), "driver")
                options = chrome.call_args.kwargs["options"]
                service = chrome.call_args.kwargs["service"]
                self.assertEqual(service.path, str(driver))
                self.assertIn("--headless", options.arguments)

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
