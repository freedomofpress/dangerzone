import os
import subprocess

import pytest
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider.base import IsolationProvider
from dangerzone.isolation_provider.dummy import Dummy

from .base import IsolationProviderTermination

# Run the tests in this module only if dummy conversion is enabled.
if not os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is not enabled", allow_module_level=True)


class DummyWait(Dummy):
    """Dummy isolation provider that spawns a blocking process."""

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        return subprocess.Popen(
            ["python3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )


@pytest.fixture
def provider_wait() -> DummyWait:
    return DummyWait()


@pytest.fixture
def provider() -> Dummy:
    return Dummy()


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

    def test_linger_unkillable(
        self,
        provider_wait: IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # We have to spawn a blocking process here, else we can't imitate an
        # "unkillable" process.
        super().test_linger_unkillable(provider_wait, mocker)
