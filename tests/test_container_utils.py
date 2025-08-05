import pathlib
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from dangerzone import errors
from dangerzone.container_utils import Runtime
from dangerzone.settings import Settings
from dangerzone import settings


def test_get_runtime_name_from_settings(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    mocker.patch("dangerzone.container_utils.Path.exists", return_value=True)

    settings = Settings()
    settings.set("container_runtime", "/opt/somewhere/docker", autosave=True)

    assert Runtime().name == "docker"


def test_get_runtime_name_linux(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch(
        "dangerzone.container_utils.shutil.which", return_value="/usr/bin/podman"
    )
    mocker.patch("dangerzone.container_utils.os.path.exists", return_value=True)
    runtime = Runtime()
    assert runtime.name == "podman"
    assert runtime.path == Path("/usr/bin/podman")


def test_get_runtime_name_non_linux(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    mocker.patch(
        "dangerzone.container_utils.shutil.which", return_value="/usr/bin/docker"
    )
    mocker.patch("dangerzone.container_utils.os.path.exists", return_value=True)
    runtime = Runtime()
    assert runtime.name == "docker"
    assert runtime.path == Path("/usr/bin/docker")

    mocker.patch("platform.system", return_value="Something else")

    runtime = Runtime()
    assert runtime.name == "docker"
    assert runtime.path == Path("/usr/bin/docker")
    assert Runtime().name == "docker"


def test_get_unsupported_runtime_name(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings = Settings()
    settings.set(
        "container_runtime", "/opt/somewhere/new-kid-on-the-block", autosave=True
    )

    with pytest.raises(errors.UnsupportedContainerRuntime):
        assert Runtime().name == "new-kid-on-the-block"


def test_get_podman_path(mocker: MockerFixture):
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


def test_create_containers_conf(mocker: MockerFixture, tmp_path: pathlib.Path):
    """Test that we don't fail when writing the containers conf file.

    Test that we can write and overwrite the config file for Podman containers, and that
    the intermediate dirs will be created.
    """
    path = tmp_path / "path" / "to" / "containers.conf"
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.container_utils.CONTAINERS_CONF_PATH", path)
    container_utils.create_containers_conf()
    conf = path.read_text()
    assert "helper_binaries_dir" in conf

    container_utils.create_containers_conf()
    assert conf == path.read_text()


def test_init_podman_command(mocker: MockerFixture):
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


def test_init_podman_command_custom_runtime(mocker: MockerFixture):
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
