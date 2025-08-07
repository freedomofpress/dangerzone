import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.main_window import MainWindow, StatusBar


@pytest.fixture
def status_bar(qtbot: QtBot, mocker: MockerFixture):
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()
    dangerzone_gui = DangerzoneGui(mock_app, dummy)
    widget = StatusBar(dangerzone_gui)
    qtbot.addWidget(widget)
    return widget


def test_status_bar_initial_state(status_bar):
    assert status_bar.message.text() == ""
    assert not status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()


def test_set_status_ok(status_bar):
    status_bar.set_status_ok("All good")
    assert status_bar.message.text() == "All good"
    assert status_bar.spinner.isHidden()
    assert status_bar.info_icon.isHidden()
    assert "color: green;" in status_bar.styleSheet()


def test_set_status_working(status_bar):
    status_bar.set_status_working("Something is happening")
    assert status_bar.message.text() == "Something is happening"
    assert not status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()
    assert "color: orange;" in status_bar.styleSheet()


def test_set_status_error(status_bar):
    status_bar.set_status_error("An error occurred")
    assert status_bar.message.text() == "An error occurred"
    assert status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()
    assert "color: red;" in status_bar.styleSheet()
