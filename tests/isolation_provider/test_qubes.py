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
    def test_out_of_ram(
        self,
        provider: Qubes,
        mocker: MockerFixture,
        monkeypatch: MonkeyPatch,
        sample_doc: str,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()

        proc = None

        def start_doc_to_pixels_proc() -> subprocess.Popen:
            proc = subprocess.Popen(
                # XXX error 126 simulates a qrexec-policy failure. Source:
                # https://github.com/QubesOS/qubes-core-qrexec/blob/fdcbfd7/daemon/qrexec-daemon.c#L1022
                ["exit 126"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
            )
            return proc

        monkeypatch.setattr(
            provider, "start_doc_to_pixels_proc", start_doc_to_pixels_proc
        )

        with pytest.raises(errors.InterruptedConversionException) as e:
            doc = Document(sample_doc)
            provider.doc_to_pixels(doc, tmpdir)
            assert provider.get_proc_exception(proc) == errors.QubesQrexecFailed  # type: ignore [arg-type]
