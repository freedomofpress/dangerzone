from __future__ import annotations

import tempfile

import pytest
from click.testing import CliRunner, Result

from dangerzone.cli import cli_main

from . import TestBase, for_each_doc

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


class TestCli(TestBase):
    def run_cli(self, *args, **kwargs) -> Result:
        return CliRunner().invoke(cli_main, *args, **kwargs)


class TestCliBasic(TestCli):
    def test_no_args(self):
        """``$ dangerzone-cli``"""
        result = self.run_cli()
        assert result.exit_code != 0

    def test_help(self):
        """``$ dangerzone-cli --help``"""
        result = self.run_cli("--help")
        assert result.exit_code == 0


class TestCliConversion(TestCliBasic):
    def test_invalid_lang(self):
        result = self.run_cli(f"{self.sample_doc} --ocr-lang piglatin")
        assert result.exit_code != 0

    @for_each_doc
    def test_formats(self, doc):
        result = self.run_cli(f'"{doc}"')
        assert result.exit_code == 0

    def test_output_filename(self):
        temp_dir = tempfile.mkdtemp(prefix="dangerzone-")
        result = self.run_cli(
            f"{self.sample_doc} --output-filename {temp_dir}/safe.pdf"
        )
        assert result.exit_code == 0

    def test_output_filename_new_dir(self):
        result = self.run_cli(
            f"{self.sample_doc} --output-filename fake-directory/my-output.pdf"
        )
        assert result.exit_code != 0

    def test_sample_not_found(self):
        result = self.run_cli("fake-directory/fake-file.pdf")
        assert result.exit_code != 0

    def test_lang_eng(self):
        result = self.run_cli(f'"{self.sample_doc}" --ocr-lang eng')
        assert result.exit_code == 0
