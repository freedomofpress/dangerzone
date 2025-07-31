import os
import platform

import pytest
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess

from dangerzone import errors
from dangerzone.container_utils import expected_image_name, init_podman_command
from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.qubes import is_qubes_native_conversion
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
    @pytest.mark.skipif(
        platform.system() not in ("Windows", "Darwin"),
        reason="macOS and Windows specific",
    )
    def test_old_docker_desktop_version_is_detected(
        self, mocker: MockerFixture, provider: Container, fp: FakeProcess
    ) -> None:
        fp.register_subprocess(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Platform.Name}}",
            ],
            stdout="Docker Desktop 1.0.0 (173100)",
        )

        mocker.patch(
            "dangerzone.isolation_provider.container.MINIMUM_DOCKER_DESKTOP",
            {"Darwin": "1.0.1", "Windows": "1.0.1"},
        )
        assert (False, "1.0.0") == provider.check_docker_desktop_version()

    @pytest.mark.skipif(
        platform.system() not in ("Windows", "Darwin"),
        reason="macOS and Windows specific",
    )
    def test_up_to_date_docker_desktop_version_is_detected(
        self, mocker: MockerFixture, provider: Container, fp: FakeProcess
    ) -> None:
        fp.register_subprocess(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Platform.Name}}",
            ],
            stdout="Docker Desktop 1.0.1 (173100)",
        )

        # Require version 1.0.1
        mocker.patch(
            "dangerzone.isolation_provider.container.MINIMUM_DOCKER_DESKTOP",
            {"Darwin": "1.0.1", "Windows": "1.0.1"},
        )
        assert (True, "1.0.1") == provider.check_docker_desktop_version()

        fp.register_subprocess(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Platform.Name}}",
            ],
            stdout="Docker Desktop 2.0.0 (173100)",
        )
        assert (True, "2.0.0") == provider.check_docker_desktop_version()

    @pytest.mark.skipif(
        platform.system() not in ("Windows", "Darwin"),
        reason="macOS and Windows specific",
    )
    def test_docker_desktop_version_failure_returns_true(
        self, mocker: MockerFixture, provider: Container, fp: FakeProcess
    ) -> None:
        fp.register_subprocess(
            [
                "docker",
                "version",
                "--format",
                "{{.Server.Platform.Name}}",
            ],
            stderr="Oopsie",
            returncode=1,
        )
        assert provider.check_docker_desktop_version() == (True, "")


class TestContainerTermination(IsolationProviderTermination):
    pass
