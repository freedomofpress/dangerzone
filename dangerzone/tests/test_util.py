import io
import os
import platform
import subprocess
import unittest
from unittest import mock
from io import StringIO
from pathlib import Path
import sys
from unittest import TestCase

from strip_ansi import strip_ansi  # type: ignore

import dangerzone.util as dzutil


class TestUtil(TestCase):

    VERSION_FILE_NAME = "version.txt"

    def setUp(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.dangerzone_dev = True

    def test_dev_mode(self):
        self.assertTrue(dzutil.dev_mode())

    def test__dev_root_path(self):
        current_dir = Path().resolve()
        root_path = dzutil._dev_root_path()
        self.assertTrue(
            current_dir.samefile(root_path),
            msg=f"{current_dir} is not the same file as {root_path}",
        )

    def test_get_resource_path(self):
        share_dir = Path("share").resolve()
        resource_path = Path(dzutil.get_resource_path(self.VERSION_FILE_NAME)).parent
        self.assertTrue(
            share_dir.samefile(resource_path),
            msg=f"{share_dir} is not the same file as {resource_path}",
        )

    @unittest.skipUnless(platform.system() == "Windows", "STARTUPINFO is for Windows")
    def test_get_subprocess_startupinfo(self):
        startupinfo = dzutil.get_subprocess_startupinfo()
        self.assertIsInstance(startupinfo, subprocess.STARTUPINFO)

    def test__get_version(self):
        version = dzutil._get_version()
        semver_pattern = (
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)("
            r"?:\.(?:0|[;1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.["
            r"0-9a-zA-Z-]+)*))?$"
        )
        self.assertRegex(
            version,
            semver_pattern,
            f"{version} is not a semantic version, see <https://semver.org>.",
        )

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_display_banner(self, mock_stdout: StringIO):
        dzutil.display_banner()  # call the test subject
        banner = mock_stdout.getvalue()
        plain_lines = [strip_ansi(line) for line in banner.splitlines()]
        with self.subTest("banner top border"):
            self.assertEqual("╭──────────────────────────╮", plain_lines[0])
        with self.subTest("banner bottom border"):
            self.assertEqual("╰──────────────────────────╯", plain_lines[14])
        with self.subTest("banner consistent dimensions"):
            width = len(plain_lines[0])
            for line in plain_lines:
                self.assertEqual(len(line), width)

    @unittest.mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_display_banner_dims(self, mock_stdout: StringIO):
        dzutil.display_banner()  # call the test subject
        banner = mock_stdout.getvalue()
        banner_lines = banner.splitlines()
