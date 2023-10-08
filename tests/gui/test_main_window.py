import os
import pathlib
import shutil
import time
import typing

from PySide6 import QtCore, QtWidgets
from pytest import MonkeyPatch, fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui import MainWindow
from dangerzone.gui import main_window as main_window_module
from dangerzone.gui import updater as updater_module
from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.main_window import ContentWidget
from dangerzone.gui.updater import UpdateReport, UpdaterThread
from dangerzone.util import get_version

from .. import sample_doc, sample_pdf
from . import qt_updater as updater
from .test_updater import assert_report_equal, default_updater_settings

##
## Widget Fixtures
##


@fixture
def content_widget(qtbot: QtBot, mocker: MockerFixture) -> ContentWidget:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()
    dz = DangerzoneGui(mock_app, dummy)
    w = ContentWidget(dz)
    qtbot.addWidget(w)
    return w


def test_default_menu(
    qtbot: QtBot,
    updater: UpdaterThread,
) -> None:
    """Check that the default menu entries are in order."""
    updater.dangerzone.settings.set("updater_check", True)

    window = MainWindow(updater.dangerzone)
    menu_actions = window.hamburger_button.menu().actions()
    assert len(menu_actions) == 3

    toggle_updates_action = menu_actions[0]
    assert toggle_updates_action.text() == "Check for updates"
    assert toggle_updates_action.isChecked()

    separator = menu_actions[1]
    assert separator.isSeparator()

    exit_action = menu_actions[2]
    assert exit_action.text() == "Exit"

    toggle_updates_action.trigger()
    assert not toggle_updates_action.isChecked()
    assert updater.dangerzone.settings.get("updater_check") == False


def test_no_update(
    qtbot: QtBot,
    updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that when no update has been detected, the user is not alerted."""
    # Check that when no update is detected, e.g., due to update cooldown, an empty
    # report is received that does not affect the menu entries.
    curtime = int(time.time())
    updater.dangerzone.settings.set("updater_check", True)
    updater.dangerzone.settings.set("updater_errors", 9)
    updater.dangerzone.settings.set("updater_last_check", curtime)

    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = True
    expected_settings["updater_errors"] = 0  # errors must be cleared
    expected_settings["updater_last_check"] = curtime

    window = MainWindow(updater.dangerzone)
    window.register_update_handler(updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")

    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    # Check that the callback function gets an empty report.
    handle_updates_spy.assert_called_once()
    assert_report_equal(handle_updates_spy.call_args.args[0], UpdateReport())

    # Check that the menu entries remain exactly the same.
    menu_actions_after = window.hamburger_button.menu().actions()
    assert menu_actions_before == menu_actions_after

    # Check that any previous update errors are cleared.
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings


def test_update_detected(
    qtbot: QtBot,
    updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that a newly detected version leads to a notification to the user."""
    updater.dangerzone.settings.set("updater_check", True)
    updater.dangerzone.settings.set("updater_last_check", 0)
    updater.dangerzone.settings.set("updater_errors", 9)

    # Make requests.get().json() return the following dictionary.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    mocker.patch("dangerzone.gui.updater.requests.get")
    requests_mock = updater_module.requests.get
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    window = MainWindow(updater.dangerzone)
    window.register_update_handler(updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")
    load_svg_spy = mocker.spy(window, "load_svg_image")

    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    handle_updates_spy.assert_called_once()
    assert_report_equal(
        handle_updates_spy.call_args.args[0], UpdateReport("99.9.9", "<p>changelog</p>")
    )

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = True
    expected_settings["updater_last_check"] = updater.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_latest_version"] = "99.9.9"
    expected_settings["updater_latest_changelog"] = "<p>changelog</p>"
    expected_settings["updater_errors"] = 0
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that the hamburger icon has changed with the expected SVG image.
    assert load_svg_spy.call_count == 2
    assert load_svg_spy.call_args_list[0].args[0] == "hamburger_menu_update_success.svg"
    assert (
        load_svg_spy.call_args_list[1].args[0]
        == "hamburger_menu_update_dot_available.svg"
    )

    # Check that new menu entries have been added.
    menu_actions_after = window.hamburger_button.menu().actions()
    assert len(menu_actions_after) == 5
    assert menu_actions_after[2:] == menu_actions_before

    success_action = menu_actions_after[0]
    assert success_action.text() == "New version available"

    separator = menu_actions_after[1]
    assert separator.isSeparator()

    # Check that clicking in the new menu entry, opens a dialog.
    update_dialog_spy = mocker.spy(main_window_module, "UpdateDialog")

    def check_dialog() -> None:
        dialog = updater.dangerzone.app.activeWindow()

        update_dialog_spy.assert_called_once()
        kwargs = update_dialog_spy.call_args.kwargs
        assert "99.9.9" in kwargs["title"]
        assert "dangerzone.rocks" in kwargs["intro_msg"]
        assert not kwargs["middle_widget"].toggle_button.isChecked()
        collapsible_box = kwargs["middle_widget"]
        text_browser = (
            collapsible_box.layout().itemAt(1).widget().layout().itemAt(0).widget()
        )
        assert collapsible_box.toggle_button.text() == "What's New?"
        assert text_browser.toPlainText() == "changelog"

        height_initial = dialog.sizeHint().height()
        width_initial = dialog.sizeHint().width()

        # Collapse the "What's New" section and ensure that the dialog's height
        # increases.
        with qtbot.waitSignal(collapsible_box.toggle_animation.finished) as blocker:
            collapsible_box.toggle_button.click()

        assert dialog.sizeHint().height() > height_initial
        assert dialog.sizeHint().width() == width_initial

        # Uncollapse the "What's New" section, and ensure that the dialog's height gets
        # back to the original value.
        with qtbot.waitSignal(collapsible_box.toggle_animation.finished) as blocker:
            collapsible_box.toggle_button.click()

        assert dialog.sizeHint().height() == height_initial
        assert dialog.sizeHint().width() == width_initial

        dialog.close()

    QtCore.QTimer.singleShot(500, check_dialog)
    success_action.trigger()

    # FIXME: We should check the content of the dialog here.


def test_update_error(
    qtbot: QtBot,
    updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that an error during an update check leads to a notification to the user."""
    # Test 1 - Check that the first error does not notify the user.
    updater.dangerzone.settings.set("updater_check", True)
    updater.dangerzone.settings.set("updater_last_check", 0)
    updater.dangerzone.settings.set("updater_errors", 0)

    # Make requests.get() return an errorthe following dictionary.
    mocker.patch("dangerzone.gui.updater.requests.get")
    requests_mock = updater_module.requests.get
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]

    window = MainWindow(updater.dangerzone)
    window.register_update_handler(updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")
    load_svg_spy = mocker.spy(window, "load_svg_image")

    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    handle_updates_spy.assert_called_once()
    assert "failed" in handle_updates_spy.call_args.args[0].error

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = True
    expected_settings["updater_last_check"] = updater.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_errors"] += 1
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that the hamburger icon has not changed.
    assert load_svg_spy.call_count == 0

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 2 - Check that the second error does not notify the user either.
    updater.dangerzone.settings.set("updater_last_check", 0)
    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    assert load_svg_spy.call_count == 0

    # Check that the settings have been updated properly.
    expected_settings["updater_errors"] += 1
    expected_settings["updater_last_check"] = updater.dangerzone.settings.get(
        "updater_last_check"
    )
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 3 - Check that a third error shows a new menu entry.
    updater.dangerzone.settings.set("updater_last_check", 0)
    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    menu_actions_after = window.hamburger_button.menu().actions()
    assert len(menu_actions_after) == 5
    assert menu_actions_after[2:] == menu_actions_before

    # Check that the hamburger icon has changed with the expected SVG image.
    assert load_svg_spy.call_count == 2
    assert load_svg_spy.call_args_list[0].args[0] == "hamburger_menu_update_error.svg"
    assert (
        load_svg_spy.call_args_list[1].args[0] == "hamburger_menu_update_dot_error.svg"
    )

    error_action = menu_actions_after[0]
    assert error_action.text() == "Update error"

    separator = menu_actions_after[1]
    assert separator.isSeparator()

    # Check that clicking in the new menu entry, opens a dialog.
    update_dialog_spy = mocker.spy(main_window_module, "UpdateDialog")

    def check_dialog() -> None:
        dialog = updater.dangerzone.app.activeWindow()

        update_dialog_spy.assert_called_once()
        kwargs = update_dialog_spy.call_args.kwargs
        assert kwargs["title"] == "Update check error"
        assert "Something went wrong" in kwargs["intro_msg"]
        assert "dangerzone.rocks" in kwargs["intro_msg"]
        assert not kwargs["middle_widget"].toggle_button.isChecked()
        collapsible_box = kwargs["middle_widget"]
        text_browser = (
            collapsible_box.layout().itemAt(1).widget().layout().itemAt(0).widget()
        )
        assert collapsible_box.toggle_button.text() == "Error Details"
        assert "Encountered an exception" in text_browser.toPlainText()
        assert "failed" in text_browser.toPlainText()

        dialog.close()

    QtCore.QTimer.singleShot(500, check_dialog)
    error_action.trigger()


##
## Document Selection tests
##


def test_change_document_button(
    content_widget: ContentWidget,
    qtbot: QtBot,
    mocker: MockerFixture,
    sample_pdf: str,
    sample_doc: str,
    tmp_path: pathlib.Path,
) -> None:
    # Setup first doc selection
    file_dialog_mock = mocker.MagicMock()
    file_dialog_mock.selectedFiles.return_value = (sample_pdf,)
    content_widget.doc_selection_widget.file_dialog = file_dialog_mock

    # Select first file
    with qtbot.waitSignal(content_widget.documents_added):
        qtbot.mouseClick(
            content_widget.doc_selection_widget.dangerous_doc_button,
            QtCore.Qt.MouseButton.LeftButton,
        )
        file_dialog_mock.accept()

    # Setup doc change
    shutil.copy(sample_doc, tmp_path)
    tmp_sample_doc = tmp_path / os.path.basename(sample_doc)
    file_dialog_mock.selectedFiles.return_value = (tmp_sample_doc,)

    # When clicking on "select docs" button
    with qtbot.waitSignal(content_widget.documents_added):
        qtbot.mouseClick(
            content_widget.settings_widget.change_selection_button,
            QtCore.Qt.MouseButton.LeftButton,
        )
        file_dialog_mock.accept()

    # Then two dialogs should have been open
    assert file_dialog_mock.exec.call_count is 2
    assert file_dialog_mock.selectedFiles.call_count is 2

    # Then the final document should be only the second one
    docs = [
        doc.input_filename
        for doc in content_widget.dangerzone.get_unconverted_documents()
    ]
    assert len(docs) is 1
    assert docs[0] == str(tmp_sample_doc)
