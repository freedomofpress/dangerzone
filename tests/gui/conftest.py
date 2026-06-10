import os
from pathlib import Path
from typing import List

import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--onscreen",
        action="store_true",
        default=False,
        help="Run GUI tests with the system display instead of offscreen rendering",
    )


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("--onscreen", default=False):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_collection_modifyitems(items: List) -> None:
    for item in items:
        if Path(item.fspath).is_relative_to(Path(__file__).parent):
            item.add_marker(pytest.mark.xdist_group("gui"))


from dangerzone.gui.logic import DangerzoneGui
from dangerzone.isolation_provider.dummy import Dummy


@pytest.fixture
def dangerzone_gui(
    qtbot: QtBot, mocker: MockerFixture, tmp_path: Path
) -> DangerzoneGui:
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock(spec=Dummy)
    return DangerzoneGui(mock_app, dummy)
