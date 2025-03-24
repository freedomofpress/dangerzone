from pathlib import Path
from typing import Optional

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture

from dangerzone import util
from dangerzone.gui import Application
from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.updater import UpdaterThread
from dangerzone.isolation_provider.dummy import Dummy


def get_qt_app() -> Application:
    if Application.instance() is None:  # type: ignore [call-arg]
        return Application()
    else:
        return Application.instance()  # type: ignore [call-arg]


def generate_isolated_updater(
    tmp_path: Path,
    mocker: MockerFixture,
    mock_app: bool = False,
) -> UpdaterThread:
    """Generate an Updater class with its own settings."""
    app = mocker.MagicMock() if mock_app else get_qt_app()

    dummy = Dummy()
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)

    dangerzone = DangerzoneGui(app, isolation_provider=dummy)
    updater = UpdaterThread(dangerzone)
    return updater


@pytest.fixture
def updater(tmp_path: Path, mocker: MockerFixture) -> UpdaterThread:
    return generate_isolated_updater(tmp_path, mocker, mock_app=True)


@pytest.fixture
def qt_updater(tmp_path: Path, mocker: MockerFixture) -> UpdaterThread:
    return generate_isolated_updater(tmp_path, mocker, mock_app=False)
