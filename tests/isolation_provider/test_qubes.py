import pytest

from dangerzone.isolation_provider.qubes import Qubes

from .. import sanitized_text, uncommon_text
from .base import IsolationProviderTest


@pytest.fixture
def provider() -> Qubes:
    return Qubes()


class TestQubes(IsolationProviderTest):
    pass
