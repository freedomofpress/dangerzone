import os
import platform
from typing import Generator

import pytest

from dangerzone import container_utils, errors
from dangerzone.container_utils import expected_image_name, init_podman_command
from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion
from dangerzone.podman import machine

from .base import IsolationProviderTermination, IsolationProviderTest

pytestmark = pytest.mark.xdist_group("container")

# Run the tests in this module only if we can spawn containers.
if is_qubes_native_conversion():
    pytest.skip("Qubes native conversion is enabled", allow_module_level=True)
elif os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is enabled", allow_module_level=True)


@pytest.fixture(scope="session", autouse=True)
def ensure_container_image() -> Generator[None, None, None]:
    """Ensure an image is loaded and tagged propertly before running tests"""
    on_podman_machine = platform.system() != "Linux"
    if on_podman_machine:
        m = machine.PodmanMachineManager()
        m.init()
        m.start()

    image_name = expected_image_name()
    try:
        container_utils.get_local_image_digest()
    except errors.ImageNotPresentException:
        image_id = container_utils.load_image_tarball()
        init_podman_command().run(["tag", image_id, image_name])

    yield

    if on_podman_machine:
        machine.PodmanMachineManager().stop()


@pytest.fixture
def provider(skip_image_verification: None) -> Container:
    return Container()


@pytest.fixture
def runtime_path() -> str:
    return str(init_podman_command().runner.podman_path)


class TestContainer(IsolationProviderTest):
    pass


class TestContainerTermination(IsolationProviderTermination):
    pass
