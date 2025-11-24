import pathlib
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from dangerzone import container_utils, settings


def test_get_podman_path(mocker: MockerFixture) -> None:
    """Test that we get the correct Podman path, depending on the distro.

    We should be getting the default Podman installation (None) on Linux, and the
    vendored path on Windows/macOS. On Windows specifically, it should end with .exe.
    """
    mocker.patch("platform.system", return_value="Linux")
    assert container_utils.get_podman_path() is None

    mocker.patch("platform.system", return_value="Windows")
    path = container_utils.get_podman_path()
    assert str(path).endswith("podman.exe")
    assert "vendor" in str(path)

    mocker.patch("platform.system", return_value="Darwin")
    path = container_utils.get_podman_path()
    assert str(path).endswith("podman")
    assert "vendor" in str(path)


def test_create_containers_conf(mocker: MockerFixture, tmp_path: pathlib.Path) -> None:
    """Test that we don't fail when writing the containers conf file.

    Test that we can write and overwrite the config file for Podman containers, and that
    the intermediate dirs will be created.
    """
    seccomp_path = tmp_path / "seccomp.json"
    mocker.patch("dangerzone.container_utils.SECCOMP_PATH", seccomp_path)
    mocker.patch("os.cpu_count", return_value=4)

    path = tmp_path / "path" / "to" / "containers.conf"
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.container_utils.CONTAINERS_CONF_PATH", path)
    container_utils.create_containers_conf()
    conf = path.read_text()
    assert "helper_binaries_dir" in conf
    assert "cpus=4" in conf
    assert f'volumes=["{tmp_path}:{tmp_path}:ro"]'.replace("\\", "\\\\") in conf

    container_utils.create_containers_conf()
    assert conf == path.read_text()


def test_init_podman_command(mocker: MockerFixture) -> None:
    cmd = mocker.patch("dangerzone.container_utils.PodmanCommand")

    mocker.patch("platform.system", return_value="Linux")
    container_utils.init_podman_command.cache_clear()
    container_utils.init_podman_command()
    cmd.assert_called_once_with(path=None, env=None, options=None)

    for distro in ["Windows", "Darwin"]:
        mocker.patch("platform.system", return_value=distro)
        cmd.reset_mock()
        container_utils.init_podman_command.cache_clear()
        container_utils.init_podman_command()
        kwargs = cmd.call_args.kwargs
        assert "vendor" in str(kwargs["path"])
        assert kwargs["env"]["CONTAINERS_CONF"] is not None
        assert kwargs["options"] is not None


def test_init_podman_command_custom_runtime(mocker: MockerFixture) -> None:
    # Test custom runtime
    # Test Windows/macOS Podman command (env, connection)
    # Test Linux Podman
    mocker.patch("pathlib.Path.is_file", return_value=True)
    mocker.patch("pathlib.Path.exists", return_value=True)
    runtime = "/some/path/to/podman"
    settings.Settings().set_custom_runtime(runtime)
    cmd = mocker.patch("dangerzone.container_utils.PodmanCommand")

    for distro in ["Linux", "Windows", "Darwin"]:
        cmd.reset_mock()
        mocker.patch("platform.system", return_value=distro)
        container_utils.init_podman_command.cache_clear()
        container_utils.init_podman_command()
        cmd.assert_called_once_with(path=pathlib.Path(runtime), env=None, options=None)

        # Second attempt, should be cached
        cmd.reset_mock()
        container_utils.init_podman_command()
        cmd.assert_not_called()


def test_list_containers(mocker: MockerFixture) -> None:
    """Test that list_containers returns the correct containers."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = (
        "dangerzone-container1\ndangerzone-container2\nother-container"
    )

    # Call the function
    containers = container_utils.list_containers()

    # Check the result
    assert containers == ["dangerzone-container1", "dangerzone-container2"]
    mock_podman.return_value.run.assert_called_once_with(
        ["ps", "-a", "--format", "{{ .Names }}"]
    )


def test_list_containers_empty(mocker: MockerFixture) -> None:
    """Test that list_containers returns an empty list if there are no containers."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = ""

    # Call the function
    containers = container_utils.list_containers()

    # Check the result
    assert containers == []


def test_kill_container(mocker: MockerFixture) -> None:
    """Test that kill_container calls the correct podman command."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

    # Call the function
    container_utils.kill_container("test-container")

    # Check the result
    mock_podman.return_value.run.assert_called_once_with(
        ["kill", "test-container"], check=False, timeout=container_utils.TIMEOUT_KILL
    )


def test_kill_container_timeout(mocker: MockerFixture, caplog: Any) -> None:
    """Test that kill_container logs a warning on timeout."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.side_effect = subprocess.TimeoutExpired(
        "kill", container_utils.TIMEOUT_KILL
    )

    # Call the function
    container_utils.kill_container("test-container")

    # Check the log
    assert "Could not kill container 'test-container'" in caplog.text


def test_kill_container_exception(mocker: MockerFixture, caplog: Any) -> None:
    """Test that kill_container logs an error on exception."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.side_effect = Exception("test error")

    # Call the function
    container_utils.kill_container("test-container")

    # Check the log
    assert (
        "Unexpected error occurred while killing container 'test-container'"
        in caplog.text
    )


def test_load_image_tarball(mocker: MockerFixture) -> None:
    """Test that we can load a tarball and get the digest."""
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = "Loaded image: sha256:mydigest"
    digest = container_utils.load_image_tarball(pathlib.Path("/fake/path"))
    assert digest == "sha256:mydigest"


def test_clear_old_images_deletes_digests(mocker: MockerFixture) -> None:
    """Test that clear_old_images deletes the old image digests."""
    # Mock podman calls
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_list = mocker.patch("dangerzone.container_utils.list_image_digests")

    image_name = container_utils.expected_image_name()
    old_digests = ["sha256:old_digest_1", "sha256:old_digest_2"]
    old_digests_full = [f"{image_name}@{digest}" for digest in old_digests]
    new_digest = "sha256:new_digest"
    all_digests = old_digests + [new_digest]
    mock_list.return_value = all_digests

    # Call the function
    container_utils.clear_old_images(digest_to_keep=new_digest)

    # Check that we fetched the right digests
    mock_list.assert_called_once()

    # Check that we removed the old images
    mock_podman.return_value.run.assert_any_call(["rmi", "--force", *old_digests_full])
