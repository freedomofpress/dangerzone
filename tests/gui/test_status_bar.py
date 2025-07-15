import pytest

from dangerzone.gui.main_window import MainWindow, StatusBar


@pytest.fixture
def status_bar(qtbot, dangerzone_gui):
    widget = StatusBar(dangerzone_gui)
    qtbot.addWidget(widget)
    return widget


def test_status_bar_initial_state(status_bar):
    assert status_bar.message.text() == "Starting"
    assert not status_bar.spinner.isHidden()
    assert not status_bar.info_icon.isHidden()
    assert "color: orange;" in status_bar.styleSheet()


def test_set_status_ok(status_bar):
    status_bar.set_status_ok("All good")
    assert status_bar.message.text() == "All good"
    assert status_bar.spinner.isHidden()
    assert status_bar.info_icon.isHidden()
    assert "color: green;" in status_bar.styleSheet()


def test_set_status_warning(status_bar):
    status_bar.set_status_warning("Something is happening")
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
