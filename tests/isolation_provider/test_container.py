import os
import platform

import pytest
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess

from dangerzone import errors
from dangerzone.container_utils import expected_image_name, init_podman_command
from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion
from dangerzone.podman import machine
from dangerzone.updater import SignatureError, UpdaterError
from dangerzone.util import get_resource_path

from .base import IsolationProviderTermination, IsolationProviderTest

# Run the tests in this module only if we can spawn containers.
if is_qubes_native_conversion():
    pytest.skip("Qubes native conversion is enabled", allow_module_level=True)
elif os.environ.get("DUMMY_CONVERSION", False):
    pytest.skip("Dummy conversion is enabled", allow_module_level=True)


@pytest.fixture
def provider(skip_image_verification: None) -> Container:
    return Container()


@pytest.fixture
def runtime_path() -> str:
    return str(init_podman_command().runner.podman_path)


class TestContainer(IsolationProviderTest):
    @classmethod
    def setup_class(cls):
        if platform.system() != "Linux":
            cls.machine = machine.PodmanMachineManager()
            cls.machine.init()
            cls.machine.start()

    @classmethod
    def teardownn_class(cls):
        if platform.system() != "Linux":
            cls.stop()


class TestContainerTermination(IsolationProviderTermination):
    @classmethod
    def setup_class(cls):
        if platform.system() != "Linux":
            cls.machine = machine.PodmanMachineManager()
            cls.machine.init()
            cls.machine.start()

    @classmethod
    def teardownn_class(cls):
        if platform.system() != "Linux":
            cls.stop()
