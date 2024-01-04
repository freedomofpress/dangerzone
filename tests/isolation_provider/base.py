import os

import pytest
from colorama import Style
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider import base
from dangerzone.isolation_provider.qubes import running_on_qubes

from .. import pdf_11k_pages, sanitized_text, uncommon_text


@pytest.mark.skipif(
    os.environ.get("DUMMY_CONVERSION", False),
    reason="dummy conversions not supported",
)
@pytest.mark.skipif(not running_on_qubes(), reason="Not on a Qubes system")
class IsolationProviderTest:
    def test_max_pages_received(
        self,
        pdf_11k_pages: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        doc = Document(pdf_11k_pages)
        with pytest.raises(errors.MaxPagesException):
            success = provider._convert(doc, ocr_lang=None)
            assert not success
