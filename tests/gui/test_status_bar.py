import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.main_window import StatusBar


@pytest.fixture
def status_bar(qtbot: QtBot, mocker: MockerFixture) -> StatusBar:
    animate_svg_mock = mocker.patch("dangerzone.gui.main_window.animate_svg_image")
    animate_svg_mock.return_value = QSvgWidget()
    load_svg_mock = mocker.patch("dangerzone.gui.main_window.load_svg_image")
    load_svg_mock.return_value = QPixmap(15, 15)
    mock_app = mocker.MagicMock()
    mock_app.os_color_mode.value = "light"
    dummy = mocker.MagicMock()
    dangerzone_gui = DangerzoneGui(mock_app, dummy)
    widget = StatusBar(dangerzone_gui)
    qtbot.addWidget(widget)
    return widget


def test_status_bar_initial_state(status_bar: StatusBar) -> None:
    assert status_bar.message.text() == ""
    assert not status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()


def test_set_status_ok(status_bar: StatusBar) -> None:
    status_bar.set_status_ok("All good")
    assert status_bar.message.text() == "All good"
    assert status_bar.spinner.isHidden()
    assert status_bar.info_icon.isHidden()
    assert status_bar.message.property("style") == "status-success"


def test_set_status_working(status_bar: StatusBar) -> None:
    status_bar.set_status_working("Something is happening")
    assert status_bar.message.text() == "Something is happening"
    assert not status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()
    assert status_bar.message.property("style") == "status-attention"


def test_set_status_error(status_bar: StatusBar) -> None:
    status_bar.set_status_error("An error occurred")
    assert status_bar.message.text() == "An error occurred"
    assert status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()
    assert status_bar.message.property("style") == "status-error"


def test_status_bar_dark_mode_svgs(qtbot: QtBot, mocker: MockerFixture) -> None:
    animate_svg_image_mock = mocker.patch(
        "dangerzone.gui.main_window.animate_svg_image"
    )
    animate_svg_image_mock.return_value = QSvgWidget()
    load_svg_image_mock = mocker.patch("dangerzone.gui.main_window.load_svg_image")
    load_svg_image_mock.return_value = QPixmap(15, 15)
    mock_app = mocker.MagicMock()
    mock_app.os_color_mode.value = "dark"
    dummy = mocker.MagicMock()
    dangerzone_gui = DangerzoneGui(mock_app, dummy)
    widget = StatusBar(dangerzone_gui)
    qtbot.addWidget(widget)

    animate_svg_image_mock.assert_called_with("spinner-dark.svg", width=15, height=15)
    load_svg_image_mock.assert_called_with("info-circle-dark.svg", width=15, height=15)


def test_status_bar_light_mode_svgs(qtbot: QtBot, mocker: MockerFixture) -> None:
    animate_svg_image_mock = mocker.patch(
        "dangerzone.gui.main_window.animate_svg_image"
    )
    animate_svg_image_mock.return_value = QSvgWidget()
    load_svg_image_mock = mocker.patch("dangerzone.gui.main_window.load_svg_image")
    load_svg_image_mock.return_value = QPixmap(15, 15)
    mock_app = mocker.MagicMock()
    mock_app.os_color_mode.value = "light"
    dummy = mocker.MagicMock()
    dangerzone_gui = DangerzoneGui(mock_app, dummy)
    widget = StatusBar(dangerzone_gui)
    qtbot.addWidget(widget)

    animate_svg_image_mock.assert_called_with("spinner.svg", width=15, height=15)
    load_svg_image_mock.assert_called_with("info-circle.svg", width=15, height=15)
