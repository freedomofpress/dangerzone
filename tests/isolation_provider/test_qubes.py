import pytest

from dangerzone.isolation_provider.qubes import Qubes

# XXX Fixtures used in abstract Test class need to be imported regardless
from .. import pdf_11k_pages, sanitized_text, uncommon_text
from .base import IsolationProviderTest


@pytest.fixture
def provider() -> Qubes:
    return Qubes()


class TestQubes(IsolationProviderTest):
    pass
