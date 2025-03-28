from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from dangerzone import errors
from dangerzone.container_utils import Runtime
from dangerzone.settings import Settings


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


def test_get_unsupported_runtime_name(mocker: MockerFixture, tmp_path: Path):
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings = Settings()
    settings.set(
        "container_runtime", "/opt/somewhere/new-kid-on-the-block", autosave=True
    )

    with pytest.raises(errors.UnsupportedContainerRuntime):
        assert Runtime().name == "new-kid-on-the-block"
