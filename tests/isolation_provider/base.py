import pytest
from colorama import Style
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider import base

from .. import pdf_11k_pages, sanitized_text, uncommon_text


class IsolationProviderTest:
    def test_print_progress(
        self,
        provider: base.IsolationProvider,
        uncommon_text: str,
        sanitized_text: str,
        mocker: MockerFixture,
    ) -> None:
        """Test that the print_progress() method of our isolation providers sanitizes text.

        Iterate our isolation providers and make sure that their print_progress() methods
        sanitizes the provided text, before passing it to the logging functions and other
        callbacks.
        """
        d = Document()
        provider.progress_callback = mocker.MagicMock()
        log_info_spy = mocker.spy(base.log, "info")
        log_error_spy = mocker.spy(base.log, "error")
        _print_progress_spy = mocker.spy(provider, "_print_progress")

        for error, untrusted_text, sanitized_text in [
            (True, "normal text", "UNTRUSTED> normal text"),
            (False, "normal text", "UNTRUSTED> normal text"),
            (True, uncommon_text, "UNTRUSTED> " + sanitized_text),
            (False, uncommon_text, "UNTRUSTED> " + sanitized_text),
        ]:
            log_info_spy.reset_mock()
            log_error_spy.reset_mock()

            provider.print_progress(d, error, untrusted_text, 0)
            provider.progress_callback.assert_called_with(error, sanitized_text, 0)  # type: ignore [union-attr]
            _print_progress_spy.assert_called_with(d, error, sanitized_text, 0)
            if error:
                assert log_error_spy.call_args[0][0].endswith(
                    sanitized_text + Style.RESET_ALL
                )
                log_info_spy.assert_not_called()
            else:
                assert log_info_spy.call_args[0][0].endswith(sanitized_text)
                log_error_spy.assert_not_called()

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
