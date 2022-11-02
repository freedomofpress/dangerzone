import os
import platform
import tempfile
from pathlib import Path

import pytest

from dangerzone import errors
from dangerzone.document import Document

from . import sample_doc, unreadable_pdf


def test_input_sample_init(sample_doc: str) -> None:
    Document(sample_doc)


def test_input_sample_after(sample_doc: str) -> None:
    d = Document()
    d.input_filename = sample_doc


def test_input_file_none() -> None:
    """
    Attempts to read a document's filename when no doc has been set
    """
    d = Document()
    with pytest.raises(errors.NotSetInputFilenameException) as e:
        d.input_filename


def test_input_file_non_existing() -> None:
    with pytest.raises(errors.InputFileNotFoundException) as e:
        Document("non-existing-file.pdf")


# XXX: This is not easy to test on Windows, as the file owner can always read it.
# See also:
# https://stackoverflow.com/questions/72528318/what-file-permissions-make-a-file-unreadable-by-owner-in-windows
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_input_file_unreadable(unreadable_pdf: str) -> None:
    with pytest.raises(errors.InputFileNotReadableException) as e:
        Document(unreadable_pdf)


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_output_file_unwriteable_dir(sample_doc: str, tmp_path: Path) -> None:
    # make parent dir unwriteable
    sample_doc_safe = str(tmp_path / "document-safe.pdf")
    os.chmod(tmp_path, 0o400)
    with pytest.raises(errors.UnwriteableOutputDirException) as e:
        d = Document(sample_doc, sample_doc_safe)


def test_output(tmp_path: Path) -> None:
    pdf_file = str(tmp_path.joinpath("document.pdf"))
    d = Document()
    d.output_filename = pdf_file


def test_output_file_none() -> None:
    """
    Attempts to read a document's filename when no doc has been set
    """
    d = Document()
    with pytest.raises(errors.NotSetOutputFilenameException) as e:
        d.output_filename


def test_output_file_not_pdf(tmp_path: Path) -> None:
    docx_file = str(tmp_path.joinpath("document.docx"))
    d = Document()

    with pytest.raises(errors.NonPDFOutputFileException) as e:
        d.output_filename = docx_file

    assert not os.path.exists(docx_file)


def test_is_unconverted_by_default(sample_doc: None) -> None:
    d = Document(sample_doc)
    assert d.is_unconverted()


def test_mark_as_safe(sample_doc: str) -> None:
    d = Document(sample_doc)
    d.mark_as_safe()
    assert d.is_safe()
    assert not d.is_failed()
    assert not d.is_unconverted()


def test_mark_as_converting(sample_doc: str) -> None:
    d = Document(sample_doc)
    d.mark_as_converting()
    assert d.is_converting()


def test_mark_as_failed(sample_doc: str) -> None:
    d = Document(sample_doc)
    d.mark_as_failed()
    assert d.is_failed()
    assert not d.is_safe()
    assert not d.is_unconverted()
