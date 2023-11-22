from __future__ import annotations

import base64
import contextlib
import copy
import os
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Optional, Sequence
from unittest import mock

import pytest
from click.testing import CliRunner, Result
from strip_ansi import strip_ansi

from dangerzone.cli import cli_main, display_banner
from dangerzone.document import ARCHIVE_SUBDIR, SAFE_EXTENSION
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion

from . import TestBase, for_each_doc, for_each_external_doc, sample_pdf

# TODO explore any symlink edge cases
# TODO simulate ctrl-c, ctrl-d, SIGINT/SIGKILL/SIGTERM... (man 7 signal), etc?
# TODO validate output PDFs https://github.com/pdfminer/pdfminer.six
# TODO trigger "Invalid json returned from container"
# TODO trigger "pdf-to-pixels failed"
# TODO simulate container runtime missing
# TODO simulate container connection error
# TODO simulate container connection loss


class CLIResult(Result):
    """Wrapper class for Click results.

    This class wraps Click results and provides the following extras:
    * Assertion statements for success/failure.
    * Printing the result details, when an assertion fails.
    * The arguments of the invocation, which are not provided by the stock
    `Result` class.
    """

    @classmethod
    def reclass_click_result(cls, result: Result, args: Sequence[str]) -> CLIResult:
        result.__class__ = cls
        result.args = copy.deepcopy(args)  # type: ignore[attr-defined]
        return result  # type: ignore[return-value]

    def assert_success(self) -> None:
        """Assert that the command succeeded."""
        try:
            assert self.exit_code == 0
            assert self.exception is None
        except AssertionError:
            self.print_info()
            raise

    def assert_failure(
        self, exit_code: Optional[int] = None, message: Optional[str] = None
    ) -> None:
        """Assert that the command failed.

        By default, check that the command has returned with an exit code
        other than 0. Alternatively, the caller can check for a specific exit
        code. Also, the caller can check if the output contains an error
        message.
        """
        try:
            if exit_code is None:
                assert self.exit_code != 0
            else:
                assert self.exit_code == exit_code
            if message is not None:
                assert message in self.output
        except AssertionError:
            self.print_info()
            raise

    def print_info(self) -> None:
        """Print all the info we have for a CLI result.

        Print the string representation of the result, as well as:
        1. Command output (if any).
        2. Exception traceback (if any).
        """
        print(self)
        num_lines = len(self.output.splitlines())
        if num_lines > 0:
            print(f"Output ({num_lines} lines follow):")
            print(self.output)
        else:
            print("Output (0 lines).")

        if self.exc_info:
            print("The original traceback follows:")
            traceback.print_exception(*self.exc_info, file=sys.stdout)

    def __str__(self) -> str:
        """Return a string representation of a CLI result.

        Include the arguments of the command invocation, as well as the exit
        code and exception message.
        """
        desc = (
            f"<CLIResult args: {self.args},"  # type: ignore[attr-defined]
            f" exit code: {self.exit_code}"
        )
        if self.exception:
            desc += f", exception: {self.exception}"
        return desc


class TestCli:
    def run_cli(
        self, args: Sequence[str] | str = (), tmp_path: Optional[Path] = None
    ) -> CLIResult:
        """Run the CLI with the provided arguments.

        Callers can either provide a list of arguments (iterable), or a single
        argument (str). Note that in both cases, we don't tokenize the input
        (i.e., perform `shlex.split()`), as this is prone to errors in Windows
        environments [1]. The user must perform the tokenizaton themselves.

        [1]: https://stackoverflow.com/a/35900070
        """
        if isinstance(args, str):
            # Convert the single argument to a tuple, else Click will attempt
            # to tokenize it.
            args = (args,)

        if os.environ.get("DUMMY_CONVERSION", False):
            args = ("--unsafe-dummy-conversion", *args)

        with tempfile.TemporaryDirectory() as t:
            tmp_dir = Path(t)
            # TODO: Replace this with `contextlib.chdir()` [1], which was added in
            # Python 3.11.
            #
            # [1]: https://docs.python.org/3/library/contextlib.html#contextlib.chdir
            try:
                if tmp_path is not None:
                    cwd = os.getcwd()
                    os.chdir(tmp_path)

                with mock.patch(
                    "dangerzone.isolation_provider.container.get_tmp_dir",
                    return_value=t,
                ):
                    result = CliRunner().invoke(cli_main, args)
            finally:
                if tmp_path is not None:
                    os.chdir(cwd)

                if tmp_dir.exists():
                    stale_files = list(tmp_dir.iterdir())
                    assert not stale_files

        # XXX Print stdout so that junitXML exports with output capturing
        # actually include the stdout + stderr (they are combined into stdout)
        print(result.stdout)

        return CLIResult.reclass_click_result(result, args)


class TestCliBasic(TestCli):
    def test_no_args(self) -> None:
        """``$ dangerzone-cli``"""
        result = self.run_cli()
        result.assert_failure()

    def test_help(self) -> None:
        """``$ dangerzone-cli --help``"""
        result = self.run_cli("--help")
        result.assert_success()

    def test_display_banner(self, capfd) -> None:  # type: ignore[no-untyped-def]
        display_banner()  # call the test subject
        (out, err) = capfd.readouterr()
        plain_lines = [strip_ansi(line) for line in out.splitlines()]
        assert "╭──────────────────────────╮" in plain_lines, "missing top border"
        assert "╰──────────────────────────╯" in plain_lines, "missing bottom border"

        banner_width = len(plain_lines[0])
        for line in plain_lines:
            assert len(line) == banner_width, "banner has inconsistent width"

    def test_version(self) -> None:
        result = self.run_cli("--version")
        result.assert_success()

        with open("share/version.txt") as f:
            version = f.read().strip()
            assert version in result.stdout


class TestCliConversion(TestCliBasic):
    def test_invalid_lang(self, sample_pdf: str) -> None:
        result = self.run_cli([sample_pdf, "--ocr-lang", "piglatin"])
        result.assert_failure()

    @for_each_doc
    def test_formats(self, doc: Path) -> None:
        result = self.run_cli(str(doc))
        result.assert_success()

    def test_output_filename(self, sample_pdf: str) -> None:
        temp_dir = tempfile.mkdtemp(prefix="dangerzone-")
        output_filename = str(Path(temp_dir) / "safe.pdf")
        result = self.run_cli([sample_pdf, "--output-filename", output_filename])
        result.assert_success()

    def test_output_filename_spaces(self, sample_pdf: str) -> None:
        temp_dir = tempfile.mkdtemp(prefix="dangerzone-")
        output_filename = str(Path(temp_dir) / "safe space.pdf")
        result = self.run_cli([sample_pdf, "--output-filename", output_filename])
        result.assert_success()

    def test_output_filename_new_dir(self, sample_pdf: str) -> None:
        output_filename = str(Path("fake-directory") / "my-output.pdf")
        result = self.run_cli([sample_pdf, "--output-filename", output_filename])
        result.assert_failure()

    def test_sample_not_found(self) -> None:
        input_filename = str(Path("fake-directory") / "fake-file.pdf")
        result = self.run_cli(input_filename)
        result.assert_failure()

    def test_lang_eng(self, sample_pdf: str) -> None:
        result = self.run_cli([sample_pdf, "--ocr-lang", "eng"])
        result.assert_success()

    @pytest.mark.parametrize(
        "filename,",
        [
            "“Curly_Quotes”.pdf",  # issue 144
            "Оригинал.pdf",
            "spaces test.pdf",
        ],
    )
    def test_filenames(self, filename: str, tmp_path: Path, sample_pdf: str) -> None:
        doc_path = str(Path(tmp_path).joinpath(filename))
        shutil.copyfile(sample_pdf, doc_path)
        result = self.run_cli(doc_path)
        result.assert_success()
        assert len(os.listdir(tmp_path)) == 2

    def test_bulk(self, tmp_path: Path, sample_pdf: str) -> None:
        filenames = ["1.pdf", "2.pdf", "3.pdf"]
        file_paths = []
        for filename in filenames:
            doc_path = str(tmp_path / filename)
            shutil.copyfile(sample_pdf, doc_path)
            file_paths.append(doc_path)

        result = self.run_cli(file_paths)
        result.assert_success()
        assert len(os.listdir(tmp_path)) == 2 * len(filenames)

    def test_bulk_fail_on_output_filename(
        self, tmp_path: Path, sample_pdf: str
    ) -> None:
        filenames = ["1.pdf", "2.pdf", "3.pdf"]
        file_paths = []
        for filename in filenames:
            doc_path = str(tmp_path / filename)
            shutil.copyfile(sample_pdf, doc_path)
            file_paths.append(doc_path)

        result = self.run_cli(['--output-filename="output.pdf"'] + file_paths)
        result.assert_failure()

    def test_archive(self, tmp_path: Path, sample_pdf: str) -> None:
        test_string = "original file"

        original_doc_path = str(tmp_path / "doc.pdf")
        safe_doc_path = str(tmp_path / f"doc{SAFE_EXTENSION}")
        archived_doc_path = str(tmp_path / ARCHIVE_SUBDIR / "doc.pdf")
        shutil.copyfile(sample_pdf, original_doc_path)

        result = self.run_cli(["--archive", original_doc_path])
        result.assert_success()

        # original document has been moved to unsafe/doc.pdf
        assert not os.path.exists(original_doc_path)
        assert os.path.exists(archived_doc_path)
        assert os.path.exists(safe_doc_path)

    def test_dummy_conversion(self, tmp_path: Path, sample_pdf: str) -> None:
        result = self.run_cli([sample_pdf, "--unsafe-dummy-conversion"])

    def test_dummy_conversion_bulk(self, tmp_path: Path, sample_pdf: str) -> None:
        filenames = ["1.pdf", "2.pdf", "3.pdf"]
        file_paths = []
        for filename in filenames:
            doc_path = str(tmp_path / filename)
            shutil.copyfile(sample_pdf, doc_path)
            file_paths.append(doc_path)

        result = self.run_cli(["--unsafe-dummy-conversion", *file_paths])
        result.assert_success()


class TestExtraFormats(TestCli):
    @for_each_external_doc("*hwp*")
    def test_hancom_office(self, doc: str) -> None:
        if is_qubes_native_conversion():
            pytest.skip("HWP / HWPX formats are not supported on this platform")
        with tempfile.NamedTemporaryFile("wb", delete=False) as decoded_doc:
            with open(doc, "rb") as encoded_doc:
                decoded_doc.write(base64.b64decode(encoded_doc.read()))
                decoded_doc.flush()
        result = self.run_cli(str(decoded_doc.name))
        result.assert_success()


class TestSecurity(TestCli):
    def test_suspicious_double_dash_file(self, tmp_path: Path) -> None:
        """Protection against "dangeronze-cli *" and files named --option."""
        file_path = tmp_path / "--ocr-lang"
        file_path.touch()
        result = self.run_cli(["--ocr-lang", "eng"], tmp_path)
        result.assert_failure(message="Security: Detected CLI options that are also")

    def test_suspicious_double_dash_and_equals_file(self, tmp_path: Path) -> None:
        """Protection against "dangeronze-cli *" and files named --option=value."""
        file_path = tmp_path / "--output-filename=bad"
        file_path.touch()
        result = self.run_cli(["--output-filename=bad", "eng"], tmp_path)
        result.assert_failure(message="Security: Detected CLI options that are also")

        # TODO: Check that this applies for single dash arguments, and concatenated
        # single dash arguments, once Dangerzone supports them.
