import os
import platform
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dangerzone import errors
from dangerzone.document import ARCHIVE_SUBDIR, SAFE_EXTENSION, Document


def test_input_sample_init(sample_pdf: str) -> None:
    Document(sample_pdf)


def test_input_sample_init_archive(sample_pdf: str) -> None:
    Document(sample_pdf, archive=True)


def test_input_file_none() -> None:
    """
    Attempts to read a document's filename when no doc has been set
    """
    with pytest.raises(errors.NotSetInputFilenameException):
        _d = Document()


def test_input_file_non_existing() -> None:
    with pytest.raises(errors.InputFileNotFoundException):
        Document("non-existing-file.pdf")


# XXX: This is not easy to test on Windows, as the file owner can always read it.
# See also:
# https://stackoverflow.com/questions/72528318/what-file-permissions-make-a-file-unreadable-by-owner-in-windows
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_input_file_unreadable(unreadable_pdf: str) -> None:
    with pytest.raises(errors.InputFileNotReadableException):
        Document(unreadable_pdf)


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_output_file_unwriteable_dir(sample_pdf: str, tmp_path: Path) -> None:
    # make parent dir unwriteable
    sample_pdf_safe = str(tmp_path / "document-safe.pdf")
    os.chmod(tmp_path, 0o400)
    with pytest.raises(errors.UnwriteableOutputDirException):
        Document(sample_pdf, sample_pdf_safe)


def test_output(tmp_path: Path) -> None:
    out_path = str(tmp_path.joinpath("output.pdf"))
    d = Document(data="test")
    d.output_filename = out_path


def test_output_file_none() -> None:
    """
    Attempts to read a document's filename when no doc has been set
    """
    d = Document(data="test")
    with pytest.raises(errors.NotSetOutputFilenameException):
        _ = d.output_filename


def test_output_file_not_pdf(tmp_path: Path) -> None:
    docx_file = str(tmp_path / "document.docx")
    d = Document(data="test")

    with pytest.raises(errors.NonPDFOutputFileException):
        d.output_filename = docx_file

    assert not os.path.exists(docx_file)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
def test_illegal_output_filename_windows(tmp_path: Path) -> None:
    d = Document()

    for char in '"*:<>?':
        with pytest.raises(errors.IllegalOutputFilenameException):
            d.output_filename = str(tmp_path / f"illegal{char}name.pdf")


@pytest.mark.skipif(platform.system() != "Darwin", reason="MacOS-specific")
def test_illegal_output_filename_macos(tmp_path: Path) -> None:
    illegal_name = str(tmp_path / "illegal\\name.pdf")
    d = Document()

    with pytest.raises(errors.IllegalOutputFilenameException):
        d.output_filename = illegal_name


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_archive_unwriteable_dir(tmp_path: Path) -> None:
    doc = tmp_path / "doc.pdf"
    Path.touch(doc)
    d = Document(str(doc))

    # make archive directory unreadable
    os.chmod(tmp_path, 0o400)

    with pytest.raises(errors.UnwriteableArchiveDirException):
        d.validate_default_archive_dir()


def test_archive(mocker: MagicMock, tmp_path: Path) -> None:
    original_doc_path = str(tmp_path / "doc.pdf")
    archived_doc_path = str(tmp_path / ARCHIVE_SUBDIR / "doc.pdf")

    # Perform the archival operation two times: one with no archive dir, and one with an
    # archive dir.
    test_strings = ["original file 1", "original file 2"]
    for test_string in test_strings:
        # write some content for later verifying content integrity
        with open(original_doc_path, "w") as f:
            f.write(test_string)

        # archive the document
        d = Document(original_doc_path, archive=True)
        d.archive()

        # original document has been moved to unsafe/doc.pdf
        assert not os.path.exists(original_doc_path)
        assert os.path.exists(archived_doc_path)

        # make sure it is the proper file by comparing its content
        with open(archived_doc_path) as f:
            assert f.read() == test_string


def test_set_output_dir(sample_pdf: str, tmp_path: Path) -> None:
    d = Document(sample_pdf)
    d.set_output_dir(str(tmp_path))
    assert os.path.dirname(d.output_filename) == str(tmp_path)


def test_set_output_dir_non_existant(sample_pdf: str, tmp_path: Path) -> None:
    non_existant_path = str(tmp_path / "fake-dir")
    d = Document(sample_pdf)
    with pytest.raises(errors.NonExistantOutputDirException):
        d.set_output_dir(non_existant_path)


def test_set_output_dir_is_file(sample_pdf: str, tmp_path: Path) -> None:
    # create a file
    file_path = str(tmp_path / "file")
    with open(file_path, "w"):
        pass

    d = Document(sample_pdf)
    with pytest.raises(errors.OutputDirIsNotDirException):
        d.set_output_dir(file_path)


def test_default_output_filename(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    assert d.output_filename.endswith(SAFE_EXTENSION)


def test_set_output_filename_suffix(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    safe_extension = "-trusted.pdf"
    d.suffix = safe_extension
    assert d.output_filename.endswith(safe_extension)

    d.output_filename = "something_else.pdf"
    with pytest.raises(errors.SuffixNotApplicableException):
        d.suffix = "-new-trusted.pdf"


def test_is_unconverted_by_default(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    assert d.is_unconverted()


def test_mark_as_safe(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    d.mark_as_safe()
    assert d.is_safe()
    assert not d.is_failed()
    assert not d.is_unconverted()


def test_mark_as_converting(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    d.mark_as_converting()
    assert d.is_converting()


def test_mark_as_failed(sample_pdf: str) -> None:
    d = Document(sample_pdf)
    d.mark_as_failed()
    assert d.is_failed()
    assert not d.is_safe()
    assert not d.is_unconverted()


# --- Tests for data-based (stdin) Document ---


def test_init_with_data() -> None:
    """Document can be constructed with raw bytes data."""
    d = Document(data=b"fake pdf content")
    assert d._data == b"fake pdf content"
    assert d._input_filename is None


def test_init_data_and_filename_conflict(sample_pdf: str) -> None:
    """Providing both input_filename and data raises ValueError."""
    with pytest.raises(ValueError, match="Cannot provide both"):
        Document(input_filename=sample_pdf, data=b"fake pdf content")


def test_open_with_data() -> None:
    """Document.open() returns a BytesIO with the correct content when data is set."""
    payload = b"fake pdf content"
    d = Document(data=payload)
    with d.open() as f:
        assert f.read() == payload


def test_open_with_filename(sample_pdf: str) -> None:
    """Document.open() returns a readable file handle when input_filename is set."""
    d = Document(sample_pdf)
    with d.open() as f:
        content = f.read()
        assert len(content) > 0


def test_str_stdin() -> None:
    """str() of a data-based document returns '<stdin>'."""
    d = Document(data=b"fake pdf content")
    assert str(d) == "<stdin>"


def test_str_filename(sample_pdf: str) -> None:
    """str() of a file-based document returns the input filename."""
    d = Document(sample_pdf)
    assert str(d) == d.input_filename


def test_eq_both_data() -> None:
    """Two data-based documents with the same id are equal."""
    d1 = Document(data=b"content")
    d2 = Document(data=b"content")
    # Different ids (random), so they should NOT be equal
    assert d1 != d2


def test_eq_data_vs_file(sample_pdf: str) -> None:
    """A data-based document is never equal to a file-based document."""
    d_data = Document(data=b"content")
    d_file = Document(sample_pdf)
    assert d_data != d_file


def test_eq_file_vs_file(sample_pdf: str) -> None:
    """Two file-based documents pointing to the same file are equal."""
    d1 = Document(sample_pdf)
    d2 = Document(sample_pdf)
    assert d1 == d2


def test_hash_data_based() -> None:
    """Data-based documents hash by id, not by path."""
    d = Document(data=b"content")
    assert hash(d) == hash(d.id)


def test_hash_file_based(sample_pdf: str) -> None:
    """File-based documents hash by absolute path."""
    d = Document(sample_pdf)
    assert hash(d) == hash(str(Path(sample_pdf).absolute()))


def test_data_output_filename_not_set() -> None:
    """Data-based document without output_filename raises on access."""
    d = Document(data=b"content")
    with pytest.raises(errors.NotSetOutputFilenameException):
        _ = d.output_filename


def test_data_output_filename_set(tmp_path: Path) -> None:
    """Data-based document with output_filename works."""
    out = str(tmp_path / "safe.pdf")
    d = Document(data=b"content", output_filename=out)
    assert d.output_filename == os.path.abspath(out)
