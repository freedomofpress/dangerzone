from __future__ import annotations

import os.path
import sys
from pathlib import Path
from unittest import TestCase

from click.testing import CliRunner, Result

from dangerzone.cli import cli_main


# TODO --output-filename with spaces
# TODO explore any symlink edge cases
# TODO simulate ctrl-c, ctrl-d, SIGINT/SIGKILL/SIGTERM... (man 7 signal), etc?
# TODO validate output PDFs https://github.com/pdfminer/pdfminer.six
# TODO trigger "Invalid json returned from container"
# TODO trigger "pdf-to-pixels failed"
# TODO simulate container runtime missing
# TODO simulate container connection error
# TODO simulate container connection loss
# FIXME "/" path separator is platform-dependent, use pathlib instead


class CliTestCase(TestCase):
    SAMPLE_DIRECTORY = "test_docs"
    BASIC_SAMPLE = f"{SAMPLE_DIRECTORY}/sample.pdf"
    SAFE_SUFFIX = "-safe.pdf"

    def setUp(self):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.dangerzone_dev = True
        self.runner = CliRunner()
        # TODO Use pathlib or similar for safer file handling here
        samples_dir = Path(self.SAMPLE_DIRECTORY)
        self.samples: list[Path | str] = [
            p
            for p in samples_dir.rglob("*")
            if p.is_file() and not p.name.endswith(self.SAFE_SUFFIX)
        ]
        print(f"{self.BASIC_SAMPLE} --output-filename {self.SAMPLE_DIRECTORY}/out/my-output.pdf")
        if len(self.samples) < 10:
            raise RuntimeWarning(f"Only {len(self.samples)} samples found.")

    def invoke_runner(self, *args, **kwargs) -> Result:
        return self.runner.invoke(cli_main, *args, **kwargs)


class CliBasicTestCase(CliTestCase):
    def test_no_args(self):
        """``$ dangerzone-cli``"""
        result = self.invoke_runner()
        self.assertNotEqual(result.exit_code, 0)

    def test_help(self):
        """``$ dangerzone-cli --help``"""
        result = self.invoke_runner("--help")
        self.assertEqual(result.exit_code, 0)

    def test_version(self):
        """``$ dangerzone-cli --version``"""
        # Note: fails for now, "--version" is not yet implemented.
        result = self.invoke_runner("--version")
        self.assertEqual(result.exit_code, 0)


class CliConversionTestCase(CliTestCase):
    def test_invalid_lang(self):
        result = self.invoke_runner(f"{self.BASIC_SAMPLE} --ocr-lang piglatin")
        self.assertNotEqual(result.exit_code, 0)

    def test_samples(self):
        for sample in self.samples:
            with self.subTest(f"Convert {sample}"):
                result = self.invoke_runner(f'"{sample}"')
                self.assertEqual(result.exit_code, 0)

    def test_output_filename(self):
        result = self.invoke_runner(f"{self.BASIC_SAMPLE} --output-filename {self.SAMPLE_DIRECTORY}/out/my-output.pdf")
        self.assertEqual(result.exit_code, 0)

    def test_output_filename_new_dir(self):
        result = self.invoke_runner(f"{self.BASIC_SAMPLE} --output-filename fake-directory/my-output.pdf")
        self.assertEqual(result.exit_code, 0)

    def test_sample_not_found(self):
        result = self.invoke_runner("fake-directory/fake-file.pdf")
        self.assertEquals(result.exit_code, 1)

    def test_lang_mismatch(self):
        """Try to OCR sample.pdf (Lorem ipsum) as traditional Chinese characters."""
        # TODO how should we handle these cases?
        with self.assertWarns(RuntimeWarning):
            self.invoke_runner(f"{self.BASIC_SAMPLE} --ocr-lang chi_tra")

    def test_lang_eng(self):
        # Rewrite this case if samples in other languages or scripts are added.
        result = self.invoke_runner(f'"{self.BASIC_SAMPLE}" --ocr-lang eng')
        self.assertEqual(result.exit_code, 0)

    def test_bulk(self):
        """
        Try to convert all sample documents in one run.
        Fails for now, since bulk conversion is not yet implemented.
        """
        # FIXME Once bulk conversion is implemented, return here to expand and quote self.samples correctly.
        result = self.invoke_runner(self.samples)
        self.assertEqual(result.exit_code, 0)

    def test_bulk_input_one_name(self):
        """
        Try to convert all sample documents in one run and supplies --output-filename This should fail.
        """
        # FIXME Once bulk conversion is implemented, return here to expand and quote self.samples correctly.
        result = self.invoke_runner(self.samples + ["--output-filename sample-safe.pdf"])  # more samples than names
        self.assertNotEqual(result.exit_code, 0)

    def test_bulk_ocr_eng(self):
        """
        Try to convert all sample documents in one run and with English OCR.
        Fails for now, since bulk conversion is not yet implemented.
        """
        # FIXME Once bulk conversion is implemented, return here to expand and quote self.samples correctly.
        result = self.invoke_runner(self.samples + ["--ocr-lang eng"])
        self.assertEqual(result.exit_code, 0)
