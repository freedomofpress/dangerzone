import os
import platform
import tempfile
from pathlib import Path

import pytest

from dangerzone.document import Document
from dangerzone.errors import DocumentFilenameException

from . import sample_doc, unreadable_pdf, unwriteable_pdf


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
    with pytest.raises(DocumentFilenameException) as e:
        d.input_filename
    assert "Input filename has not been set yet" in str(e.value)


def test_input_file_non_existing() -> None:
    with pytest.raises(DocumentFilenameException) as e:
        Document("non-existing-file.pdf")
    assert "Input file not found" in str(e.value)


# XXX: This is not easy to test on Windows, as the file owner can always read it.
# See also:
# https://stackoverflow.com/questions/72528318/what-file-permissions-make-a-file-unreadable-by-owner-in-windows
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific")
def test_input_file_unreadable(unreadable_pdf: str) -> None:
    with pytest.raises(DocumentFilenameException) as e:
        Document(unreadable_pdf)
    assert "don't have permission to open the input file" in str(e.value)


def test_output_file_unwriteable(unwriteable_pdf: str) -> None:
    d = Document()
    with pytest.raises(DocumentFilenameException) as e:
        d.output_filename = unwriteable_pdf
    assert "Safe PDF filename is not writable" in str(e.value)


def test_output(tmp_path: Path) -> None:
    pdf_file = str(tmp_path.joinpath("document.pdf"))
    d = Document()
    d.output_filename = pdf_file


def test_output_file_none() -> None:
    """
    Attempts to read a document's filename when no doc has been set
    """
    d = Document()
    with pytest.raises(DocumentFilenameException) as e:
        d.output_filename
    assert "Output filename has not been set yet" in str(e.value)


def test_output_file_not_pdf(tmp_path: Path) -> None:
    docx_file = str(tmp_path.joinpath("document.docx"))
    d = Document()

    with pytest.raises(DocumentFilenameException) as e:
        d.output_filename = docx_file
    assert "Safe PDF filename must end in '.pdf'" in str(e.value)

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


def test_mark_as_failed(sample_doc: str) -> None:
    d = Document(sample_doc)
    d.mark_as_failed()
    assert d.is_failed()
    assert not d.is_safe()
    assert not d.is_unconverted()
