import os
import platform

import pytest
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess

from dangerzone import container_utils, errors
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


class TestContainer(IsolationProviderTest):
    def test_is_available_raises(self, provider: Container, fp: FakeProcess) -> None:
        """
        NotAvailableContainerTechException should be raised when
        the "podman image ls" command fails.
        """
        fp.register_subprocess(
            [container_utils.get_runtime(), "image", "ls"],
            returncode=-1,
            stderr="podman image ls logs",
        )
        with pytest.raises(errors.NotAvailableContainerTechException):
            provider.is_available()

    def test_is_available_works(self, provider: Container, fp: FakeProcess) -> None:
        """
        No exception should be raised when the "podman image ls" can return properly.
        """
        fp.register_subprocess(
            [container_utils.get_runtime(), "image", "ls"],
        )
        provider.is_available()

    def test_install_raise_if_image_cant_be_installed(
        self, mocker: MockerFixture, provider: Container, fp: FakeProcess
    ) -> None:
        """When an image installation fails, an exception should be raised"""

        fp.register_subprocess(
            [container_utils.get_runtime(), "image", "ls"],
        )

        # First check should return nothing.
        fp.register_subprocess(
            [
                container_utils.get_runtime(),
                "image",
                "list",
                "--format",
                "{{ .Tag }}",
                "dangerzone.rocks/dangerzone",
            ],
            occurrences=2,
        )

        # Make podman load fail
        mocker.patch("gzip.open", mocker.mock_open(read_data=""))

        fp.register_subprocess(
            [container_utils.get_runtime(), "load"],
            returncode=-1,
        )

        with pytest.raises(errors.ImageInstallationException):
            provider.install()

    def test_install_raises_if_still_not_installed(
        self, mocker: MockerFixture, provider: Container, fp: FakeProcess
    ) -> None:
        """When an image keep being not installed, it should return False"""

        fp.register_subprocess(
            [container_utils.get_runtime(), "image", "ls"],
        )

        # First check should return nothing.
        fp.register_subprocess(
            [
                container_utils.get_runtime(),
                "image",
                "list",
                "--format",
                "{{ .Tag }}",
                "dangerzone.rocks/dangerzone",
            ],
            occurrences=2,
        )

        # Patch gzip.open and podman load so that it works
        mocker.patch("gzip.open", mocker.mock_open(read_data=""))
        fp.register_subprocess(
            [container_utils.get_runtime(), "load"],
        )
        with pytest.raises(errors.ImageNotPresentException):
            provider.install()

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

    @pytest.mark.skipif(
        platform.system() != "Linux",
        reason="Linux specific",
    )
    def test_linux_skips_desktop_version_check_returns_true(
        self, mocker: MockerFixture, provider: Container
    ) -> None:
        assert (True, "") == provider.check_docker_desktop_version()


class TestContainerTermination(IsolationProviderTermination):
    pass
