from pathlib import Path

from pytest_mock import MockerFixture

from dangerzone.container_utils import get_runtime_name
from dangerzone.settings import Settings


def test_get_runtime_name_from_settings(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)

    settings = Settings()
    settings.set("container_runtime", "new-kid-on-the-block", autosave=True)

    assert get_runtime_name() == "new-kid-on-the-block"


def test_get_runtime_name_linux(mocker: MockerFixture) -> None:
    mocker.patch("platform.system", return_value="Linux")
    assert get_runtime_name() == "podman"


def test_get_runtime_name_non_linux(mocker: MockerFixture) -> None:
    mocker.patch("platform.system", return_value="Windows")
    assert get_runtime_name() == "docker"

    mocker.patch("platform.system", return_value="Something else")
    assert get_runtime_name() == "docker"
