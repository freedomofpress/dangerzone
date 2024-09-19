import os
import subprocess
import time

import pytest
from pytest_mock import MockerFixture

from dangerzone.document import Document
from dangerzone.isolation_provider import base
from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion

from .base import IsolationProviderTermination, IsolationProviderTest

# Run the tests in this module only if we can spawn containers.
if is_qubes_native_conversion():
    pytest.skip("Qubes native conversion is enabled", allow_module_level=True)
elif os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is enabled", allow_module_level=True)


@pytest.fixture
def provider() -> Container:
    return Container()


class ContainerWait(Container):
    """Container isolation provider that blocks until the container has started."""

    def exec_container(self, *args, **kwargs):  # type: ignore [no-untyped-def]
        # Check every 100ms if a container with the expected name has showed up.
        # Else, closing the file descriptors may not work.
        name = kwargs["name"]
        runtime = self.get_runtime()
        p = super().exec_container(*args, **kwargs)
        for i in range(50):
            containers = subprocess.run(
                [runtime, "ps"], capture_output=True
            ).stdout.decode()
            if name in containers:
                return p
            time.sleep(0.1)

        raise RuntimeError(f"Container {name} did not start within 5 seconds")


@pytest.fixture
def provider_wait() -> ContainerWait:
    return ContainerWait()


class TestContainer(IsolationProviderTest):
    pass


class TestContainerTermination(IsolationProviderTermination):
    def test_linger_runtime_kill(
        self,
        provider_wait: base.IsolationProvider,
        mocker: MockerFixture,
    ) -> None:
        # Check that conversions that remain stuck on `docker|podman kill` are
        # terminated forcefully.
        doc = Document()
        provider_wait.progress_callback = mocker.MagicMock()
        get_proc_exception_spy = mocker.spy(provider_wait, "get_proc_exception")
        terminate_proc_spy = mocker.spy(provider_wait, "terminate_doc_to_pixels_proc")
        popen_kill_spy = mocker.spy(subprocess.Popen, "kill")

        # Switch the subprocess.run() function with a patched function that
        # intercepts the `kill` command and switches it with `wait` instead. This way,
        # we emulate a `docker|podman kill` command that has hang.
        orig_subprocess_run = subprocess.run

        def patched_subprocess_run(*args, **kwargs):  # type: ignore [no-untyped-def]
            assert len(args) == 1
            cmd = args[0]
            if cmd[1] == "kill":
                # Switch the `kill` command with `wait`, thereby triggering a timeout.
                cmd[1] = "wait"

                # Make sure that a timeout has been specified, and make it 0, so that
                # the test ends us quickly as possible.
                assert "timeout" in kwargs
                kwargs[timeout] = 0

                # Make sure that the modified command times out.
                with pytest.raises(subprocess.TimeoutExpired):
                    orig_subprocess_run(cmd, **kwargs)
            else:
                return orig_subprocess_run(*args, **kwargs)

        mocker.patch("subprocess.run", patched_subprocess_run)

        with provider_wait.doc_to_pixels_proc(doc, timeout_grace=0) as proc:
            # We purposefully do nothing here, so that the process remains running.
            pass

        get_proc_exception_spy.assert_not_called()
        terminate_proc_spy.assert_called()
        popen_kill_spy.assert_called()
        assert proc.poll() is not None
