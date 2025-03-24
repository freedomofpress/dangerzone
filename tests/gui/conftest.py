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
    monkeypatch: MonkeyPatch,
    app_mocker: Optional[MockerFixture] = None,
) -> UpdaterThread:
    """Generate an Updater class with its own settings."""
    if app_mocker:
        app = app_mocker.MagicMock()
    else:
        app = get_qt_app()

    dangerzone = DangerzoneGui(app, isolation_provider=Dummy())
    updater = UpdaterThread(dangerzone)
    return updater


@pytest.fixture
def updater(
    tmp_path: Path, monkeypatch: MonkeyPatch, mocker: MockerFixture, mock_settings: Path
) -> UpdaterThread:
    return generate_isolated_updater(tmp_path, monkeypatch, mocker)


@pytest.fixture
def qt_updater(
    tmp_path: Path, monkeypatch: MonkeyPatch, mock_settings: Path
) -> UpdaterThread:
    return generate_isolated_updater(tmp_path, monkeypatch)
