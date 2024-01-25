import os
import subprocess

import pytest
from colorama import Style
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider import base
from dangerzone.isolation_provider.qubes import running_on_qubes

from .. import (
    pdf_11k_pages,
    sample_bad_height,
    sample_bad_width,
    sample_doc,
    sanitized_text,
    uncommon_text,
)


@pytest.mark.skipif(
    os.environ.get("DUMMY_CONVERSION", False),
    reason="dummy conversions not supported",
)
@pytest.mark.skipif(not running_on_qubes(), reason="Not on a Qubes system")
class IsolationProviderTest:
    def test_max_pages_server_enforcement(
        self,
        pdf_11k_pages: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        monkeypatch: MonkeyPatch,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        doc = Document(pdf_11k_pages)

        proc = None
        provider.old_start_doc_to_pixels_proc = provider.start_doc_to_pixels_proc  # type: ignore [attr-defined]

        def start_doc_to_pixels_proc() -> subprocess.Popen:
            proc = provider.old_start_doc_to_pixels_proc()  # type: ignore [attr-defined]
            return proc

        monkeypatch.setattr(
            provider, "start_doc_to_pixels_proc", start_doc_to_pixels_proc
        )
        with pytest.raises(errors.InterruptedConversionException):
            provider.doc_to_pixels(doc, tmpdir)
            assert provider.get_proc_exception(proc) == errors.MaxPagesException  # type: ignore [arg-type]

    def test_max_pages_client_enforcement(
        self,
        sample_doc: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        mocker.patch(
            "dangerzone.conversion.errors.MAX_PAGES", 1
        )  # sample_doc has 4 pages > 1
        doc = Document(sample_doc)
        with pytest.raises(errors.MaxPagesException):
            provider.doc_to_pixels(doc, tmpdir)

    def test_max_dimensions(
        self,
        sample_bad_width: str,
        sample_bad_height: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        with pytest.raises(errors.MaxPageWidthException):
            provider.doc_to_pixels(Document(sample_bad_width), tmpdir)
        with pytest.raises(errors.MaxPageHeightException):
            provider.doc_to_pixels(Document(sample_bad_height), tmpdir)
