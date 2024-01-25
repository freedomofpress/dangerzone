import itertools
import json
from typing import Any, Dict

import pytest
from pytest_mock import MockerFixture

from dangerzone.document import Document
from dangerzone.isolation_provider.container import Container

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
def provider() -> Container:
    return Container()


class TestContainer(IsolationProviderTest):
    pass
