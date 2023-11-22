import signal
import subprocess
import time

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider.base import IsolationProvider
from dangerzone.isolation_provider.qubes import Qubes, running_on_qubes

# XXX Fixtures used in abstract Test class need to be imported regardless
from .. import (
    pdf_11k_pages,
    sample_bad_height,
    sample_bad_width,
    sample_doc,
    sanitized_text,
    uncommon_text,
)
from .base import IsolationProviderTest


@pytest.fixture
def provider() -> Qubes:
    return Qubes()


@pytest.mark.skipif(not running_on_qubes(), reason="Not on a Qubes system")
class TestQubes(IsolationProviderTest):
    def test_max_pages_client_side_enforcement(
        self,
        sample_doc: str,
        provider: Qubes,
        mocker: MockerFixture,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        mocker.patch(
            "dangerzone.conversion.errors.MAX_PAGES", 1
        )  # sample_doc has 4 pages > 1
        doc = Document(sample_doc)
        with pytest.raises(errors.MaxPagesException):
            success = provider._convert(doc, ocr_lang=None)
            assert not success

    def test_max_dimensions(
        self,
        sample_bad_width: str,
        sample_bad_height: str,
        provider: Qubes,
        mocker: MockerFixture,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        with pytest.raises(errors.MaxPageWidthException):
            success = provider._convert(Document(sample_bad_width), ocr_lang=None)
            assert not success
        with pytest.raises(errors.MaxPageHeightException):
            success = provider._convert(Document(sample_bad_height), ocr_lang=None)
            assert not success

    def test_out_of_ram(
        self,
        provider: Qubes,
        mocker: MockerFixture,
        monkeypatch: MonkeyPatch,
        sample_doc: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()

        def start_doc_to_pixels_proc() -> subprocess.Popen:
            p = subprocess.Popen(
                # XXX error 126 simulates a qrexec-policy failure. Source:
                # https://github.com/QubesOS/qubes-core-qrexec/blob/fdcbfd7/daemon/qrexec-daemon.c#L1022
                ["exit 126"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            return p

        monkeypatch.setattr(
            provider, "start_doc_to_pixels_proc", start_doc_to_pixels_proc
        )

        with pytest.raises(errors.QubesQrexecFailed) as e:
            doc = Document(sample_doc)
            provider._convert(doc, ocr_lang=None)
