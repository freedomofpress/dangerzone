import os
import subprocess

import pytest
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider import base
from dangerzone.isolation_provider.qubes import running_on_qubes

TIMEOUT_STARTUP = 60  # Timeout in seconds until the conversion sandbox starts.


@pytest.mark.skipif(
    os.environ.get("DUMMY_CONVERSION", False),
    reason="dummy conversions not supported",
)
class IsolationProviderTest:
    def test_max_pages_server_enforcement(
        self,
        pdf_11k_pages: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        doc = Document(pdf_11k_pages)

        p = provider.start_doc_to_pixels_proc(doc)
        with pytest.raises(errors.ConverterProcException):
            provider.doc_to_pixels(doc, tmpdir, p)
            assert provider.get_proc_exception(p) == errors.MaxPagesException

    def test_max_pages_client_enforcement(
        self,
        sample_doc: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        mocker.patch(
            "dangerzone.conversion.errors.MAX_PAGES", 1
        )  # sample_doc has 4 pages > 1
        doc = Document(sample_doc)
        p = provider.start_doc_to_pixels_proc(doc)
        with pytest.raises(errors.MaxPagesException):
            provider.doc_to_pixels(doc, tmpdir, p)

    def test_max_dimensions(
        self,
        sample_bad_width: str,
        sample_bad_height: str,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
        tmpdir: str,
    ) -> None:
        provider.progress_callback = mocker.MagicMock()
        doc = Document(sample_bad_width)
        p = provider.start_doc_to_pixels_proc(doc)
        with pytest.raises(errors.MaxPageWidthException):
            provider.doc_to_pixels(doc, tmpdir, p)

        doc = Document(sample_bad_height)
        p = provider.start_doc_to_pixels_proc(doc)
        with pytest.raises(errors.MaxPageHeightException):
            provider.doc_to_pixels(doc, tmpdir, p)


class IsolationProviderTermination:
    """Test various termination-related scenarios.

    Test how the isolation provider code handles various uncommon scenarios, where the
    conversion process may still linger:
    1. Successfully completed conversions
    2. Successful conversions that linger for a little longer.
    3. Successful conversions that linger and must be killed.
    4. Successful conversions that linger and cannot be killed.
    5. Failed conversions that have completed.
    6. Failed conversions that still linger.
    """

    def test_completed(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that we don't need to terminate any process, if the conversion completes
        # successfully.
        doc = Document()
        provider.progress_callback = mocker.MagicMock()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        terminate_proc_spy = mocker.spy(provider, "terminate_doc_to_pixels_proc")
        popen_kill_spy = mocker.spy(subprocess.Popen, "kill")

        with provider.doc_to_pixels_proc(doc) as proc:
            assert proc.stdin
            proc.stdin.close()
            proc.wait(TIMEOUT_STARTUP)

        get_proc_exception_spy.assert_not_called()
        terminate_proc_spy.assert_not_called()
        popen_kill_spy.assert_not_called()
        assert proc.poll() is not None

    def test_linger_terminate(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that successful conversions that linger for a little while are
        # terminated gracefully.
        doc = Document()
        provider.progress_callback = mocker.MagicMock()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        terminate_proc_spy = mocker.spy(provider, "terminate_doc_to_pixels_proc")
        popen_kill_spy = mocker.spy(subprocess.Popen, "kill")

        with provider.doc_to_pixels_proc(doc) as proc:
            # We purposefully do nothing here, so that the process remains running.
            pass

        get_proc_exception_spy.assert_not_called()
        terminate_proc_spy.assert_called()
        popen_kill_spy.assert_not_called()
        assert proc.poll() is not None

    def test_linger_kill(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that successful conversions that cannot be terminated gracefully, are
        # killed forcefully.
        doc = Document()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        # We mock the terminate_doc_to_pixels_proc() method, so that the process must be
        # killed.
        terminate_proc_mock = mocker.patch.object(
            provider, "terminate_doc_to_pixels_proc", return_value=None
        )
        kill_pg_spy = mocker.spy(base, "kill_process_group")

        with provider.doc_to_pixels_proc(doc, timeout_grace=0) as proc:
            pass

        get_proc_exception_spy.assert_not_called()
        terminate_proc_mock.assert_called()
        kill_pg_spy.assert_called()
        assert proc.poll() is not None

    def test_linger_unkillable(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that if a conversion process cannot be killed, at least it will not
        # block the operation.
        doc = Document()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        # We mock both the terminate_doc_to_pixels_proc() method, and our kill
        # invocation, so that the process will seem as unkillable.
        terminate_proc_orig = provider.terminate_doc_to_pixels_proc
        terminate_proc_mock = mocker.patch.object(
            provider, "terminate_doc_to_pixels_proc", return_value=None
        )
        kill_pg_mock = mocker.patch(
            "dangerzone.isolation_provider.base.kill_process_group", return_value=None
        )

        with provider.doc_to_pixels_proc(doc, timeout_grace=0, timeout_force=0) as proc:
            pass

        get_proc_exception_spy.assert_not_called()
        terminate_proc_mock.assert_called()
        kill_pg_mock.assert_called()
        assert proc.poll() is None

        # Reset the function to the original state.
        provider.terminate_doc_to_pixels_proc = terminate_proc_orig  # type: ignore [method-assign]

        # Really kill the spawned process, so that it doesn't linger after the tests
        # complete.
        provider.ensure_stop_doc_to_pixels_proc(doc, proc)
        assert proc.poll() is not None

    def test_failed(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that we don't need to terminate any process, if the conversion fails.
        # However, we should be able to get the return code.
        doc = Document()
        provider.progress_callback = mocker.MagicMock()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        terminate_proc_spy = mocker.spy(provider, "terminate_doc_to_pixels_proc")
        popen_kill_spy = mocker.spy(subprocess.Popen, "kill")

        with pytest.raises(errors.DocFormatUnsupported):
            with provider.doc_to_pixels_proc(doc, timeout_exception=0) as proc:
                assert proc.stdin
                # Sending an invalid file to the conversion process should report it as
                # an unsupported format.
                proc.stdin.write(b"A" * 9)
                proc.stdin.close()
                proc.wait(TIMEOUT_STARTUP)
                raise errors.ConverterProcException

        get_proc_exception_spy.assert_called()
        assert isinstance(
            get_proc_exception_spy.spy_return, errors.DocFormatUnsupported
        )
        terminate_proc_spy.assert_not_called()
        popen_kill_spy.assert_not_called()
        assert proc.poll() is not None

    def test_failed_linger(
        self,
        provider: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that if the failed process has not exited, the error code that will be
        # returned is UnexpectedExceptionError.
        doc = Document()
        provider.progress_callback = mocker.MagicMock()
        get_proc_exception_spy = mocker.spy(provider, "get_proc_exception")
        terminate_proc_spy = mocker.spy(provider, "terminate_doc_to_pixels_proc")
        popen_kill_spy = mocker.spy(subprocess.Popen, "kill")

        with pytest.raises(errors.UnexpectedConversionError):
            with provider.doc_to_pixels_proc(doc, timeout_exception=0) as proc:
                raise errors.ConverterProcException

        get_proc_exception_spy.assert_called()
        assert isinstance(
            get_proc_exception_spy.spy_return, errors.UnexpectedConversionError
        )
        terminate_proc_spy.assert_called()
        popen_kill_spy.assert_not_called()
        assert proc.poll() is not None
