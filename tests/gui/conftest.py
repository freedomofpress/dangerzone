from pathlib import Path
from typing import Optional

import pytest
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone import util
from dangerzone.gui import Application
from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.main_window import MainWindow
from dangerzone.isolation_provider.dummy import Dummy


@pytest.fixture
def dangerzone_gui(
    qtbot: QtBot, mocker: MockerFixture, tmp_path: Path
) -> DangerzoneGui:
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock(spec=Dummy)
    return DangerzoneGui(mock_app, dummy)
