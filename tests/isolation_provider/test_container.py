import os
import platform

import pytest
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess

from dangerzone import errors
from dangerzone.container_utils import CONTAINER_NAME, Runtime
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
    return str(Runtime().path)


class TestContainer(IsolationProviderTest):
    def test_is_available_raises(
        self, provider: Container, fp: FakeProcess, runtime_path: str
    ) -> None:
        """
        NotAvailableContainerTechException should be raised when
        the "podman image ls" command fails.
        """
        fp.register_subprocess(
            [runtime_path, "image", "ls"],
            returncode=-1,
            stderr="podman image ls logs",
        )
        with pytest.raises(errors.NotAvailableContainerTechException):
            provider.is_available()

    def test_is_available_works(
        self, provider: Container, fp: FakeProcess, runtime_path: str
    ) -> None:
        """
        No exception should be raised when the "podman image ls" can return properly.
        """
        fp.register_subprocess(
            [runtime_path, "image", "ls"],
        )
        provider.is_available()

    def test_install_raise_if_local_image_cant_be_installed(
        self,
        provider: Container,
        fp: FakeProcess,
        runtime_path: str,
        skip_image_verification,
        mocker: MockerFixture,
    ) -> None:
        """When an image installation fails, an exception should be raised"""

        fp.register_subprocess(
            [runtime_path, "image", "ls"],
        )

        # First check should return nothing.
        fp.register_subprocess(
            [
                runtime_path,
                "image",
                "list",
                "--format",
                "{{ .Tag }}",
                CONTAINER_NAME,
            ],
            occurrences=2,
        )
        mocker.patch(
            "dangerzone.isolation_provider.container.install_local_container_tar",
            side_effect=UpdaterError,
        )

        with pytest.raises(UpdaterError):
            provider.install(should_upgrade=False)

    def test_install_raise_if_local_image_cant_be_verified(
        self,
        provider: Container,
        runtime_path: str,
        skip_image_verification,
        mocker: MockerFixture,
    ) -> None:
        """In case an image has been installed but its signature cannot be verified, an exception should be raised"""

        mocker.patch(
            "dangerzone.isolation_provider.container.container_utils.list_image_tags",
            return_value=["a-tag"],
        )
        mocker.patch(
            "dangerzone.isolation_provider.container.verify_local_image",
            side_effect=SignatureError,
        )

        with pytest.raises(SignatureError):
            provider.install(should_upgrade=False)

    def test_install_raise_if_local_image_install_works_on_second_try(
        self,
        provider: Container,
        runtime_path: str,
        skip_image_verification,
        mocker: MockerFixture,
    ) -> None:
        """In case an image has been installed but its signature cannot be verified, an exception should be raised"""

        mocker.patch(
            "dangerzone.isolation_provider.container.container_utils.list_image_tags",
            return_value=["a-tag"],
        )
        mocker.patch(
            "dangerzone.isolation_provider.container.verify_local_image",
            side_effect=[SignatureError, True],
        )

        provider.install(should_upgrade=False)

    def test_install_upgrades_if_available(
        self,
        provider: Container,
        runtime_path: str,
        skip_image_verification,
        mocker: MockerFixture,
    ) -> None:
        """In case an image has been installed but its signature cannot be verified, an exception should be raised"""

        mocker.patch(
            "dangerzone.isolation_provider.container.container_utils.list_image_tags",
            return_value=["a-tag"],
        )
        mocker.patch(
            "dangerzone.isolation_provider.container.is_update_available",
            return_value=(True, "digest"),
        )
        upgrade = mocker.patch(
            "dangerzone.isolation_provider.container.upgrade_container_image",
        )
        mocker.patch(
            "dangerzone.isolation_provider.container.verify_local_image",
        )

        provider.install(should_upgrade=True)
        upgrade.assert_called()

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
        self, provider: Container
    ) -> None:
        assert (True, "") == provider.check_docker_desktop_version()


class TestContainerTermination(IsolationProviderTermination):
    pass
