import os
import subprocess

import pytest
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider.base import IsolationProvider
from dangerzone.isolation_provider.dummy import Dummy

from .base import IsolationProviderTermination


class DummyWait(Dummy):
    """Dummy isolation provider that spawns a blocking process."""

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        return subprocess.Popen(
            ["python3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def terminate_doc_to_pixels_proc(
        self, document: Document, p: subprocess.Popen
    ) -> None:
        p.terminate()


@pytest.fixture
def provider_wait() -> DummyWait:
    return DummyWait()


@pytest.mark.skipif(
    os.environ.get("DUMMY_CONVERSION", False) == False,
    reason="can only run for dummy conversions",
)
class TestDummyTermination(IsolationProviderTermination):

    def test_failed(
        self,
        provider_wait: IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(
            provider_wait,
            "get_proc_exception",
            return_value=errors.DocFormatUnsupported(),
        )
        super().test_failed(provider_wait, mocker)
