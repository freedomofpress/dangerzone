import os

import pytest
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.isolation_provider.base import IsolationProvider
from dangerzone.isolation_provider.dummy import Dummy

from .base import IsolationProviderTermination

# Run the tests in this module only if dummy conversion is enabled.
if not os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is not enabled", allow_module_level=True)


@pytest.fixture
def provider() -> Dummy:
    return Dummy()


class TestDummyTermination(IsolationProviderTermination):
    def test_failed(
        self,
        provider: IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(
            provider,
            "get_proc_exception",
            return_value=errors.DocFormatUnsupported(),
        )
        super().test_failed(provider, mocker)
