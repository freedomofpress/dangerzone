import os
import subprocess
import time

import pytest

from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion

# XXX Fixtures used in abstract Test class need to be imported regardless
from .. import (
    pdf_11k_pages,
    sample_bad_height,
    sample_bad_width,
    sample_doc,
    sanitized_text,
    uncommon_text,
)
from .base import IsolationProviderTermination, IsolationProviderTest


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


@pytest.mark.skipif(
    os.environ.get("DUMMY_CONVERSION", False),
    reason="cannot run for dummy conversions",
)
@pytest.mark.skipif(
    is_qubes_native_conversion(), reason="Qubes native conversion is enabled"
)
class TestContainerTermination(IsolationProviderTermination):
    pass
