import os
import pathlib
import subprocess
import time

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from dangerzone.conversion import errors
from dangerzone.document import Document
from dangerzone.isolation_provider.qubes import Qubes, is_qubes_native_conversion

from .base import IsolationProviderTermination, IsolationProviderTest

# Run the tests in this module only if we can spawn disposable qubes.
if not is_qubes_native_conversion():
    pytest.skip("Qubes native conversion is not enabled", allow_module_level=True)
elif os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is enabled", allow_module_level=True)


@pytest.fixture
def provider() -> Qubes:
    return Qubes()


class QubesWait(Qubes):
    """Qubes isolation provider that blocks until the disposable qube has started."""

    def start_doc_to_pixels_proc(self, document: Document) -> subprocess.Popen:
        # Check every 100ms if the disposable qube has started. Qubes gives us no
        # way to figure this out, but `qrexec-client-vm` has an interesting
        # property. It will start a vchan server **only** once the disposable qube
        # has started (i.e., on MSG_SERVICE_CONNECT) [1]
        #
        # While `qrexec-client-vm` does not report this either, we can snoop on its
        # open file descriptors, and see when it opens the `/dev/xen` character
        # devices. This is super flaky and probably subject to race conditions, but
        # since it's test code, we can live with it.
        #
        # [1]: https://www.qubes-os.org/doc/qrexec-internals/#domx-invoke-execution-of-qubes-service-qubesservice-in-domy
        proc = super().start_doc_to_pixels_proc(document)
        for i in range(300):
            for p in pathlib.Path(f"/proc/{proc.pid}/fd").iterdir():
                if str(p.resolve()).startswith("/dev/xen"):
                    # The `qrexec-client-vm` process has opened a `/dev/xen` character
                    # device. We can now yield control back to the caller.
                    return proc
            time.sleep(0.1)

        raise RuntimeError("Disposable qube did not start within 30 seconds")


@pytest.fixture
def provider_wait() -> QubesWait:
    return QubesWait()


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

        proc = subprocess.Popen(
            # XXX error 126 simulates a qrexec-policy failure. Source:
            # https://github.com/QubesOS/qubes-core-qrexec/blob/fdcbfd7/daemon/qrexec-daemon.c#L1022
            ["exit 126"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        with pytest.raises(errors.ConverterProcException):
            doc = Document(sample_doc)
            provider._convert(doc, tmpdir, None, proc)
            assert provider.get_proc_exception(proc) == errors.QubesQrexecFailed


class TestQubesTermination(IsolationProviderTermination):
    pass
