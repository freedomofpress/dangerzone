import os
import pathlib
import platform
import shutil
import time
from typing import List
from unittest.mock import MagicMock

from pytest import MonkeyPatch, fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone import errors
from dangerzone.document import Document
from dangerzone.gui import MainWindow
from dangerzone.gui import main_window as main_window_module
from dangerzone.gui import updater as updater_module
from dangerzone.gui.logic import DangerzoneGui

# import Pyside related objects from here to avoid duplicating import logic.
from dangerzone.gui.main_window import (
    ContentWidget,
    InstallContainerThread,
    QtCore,
    QtGui,
    WaitingWidgetContainer,
)
from dangerzone.gui.updater import UpdaterThread
from dangerzone.isolation_provider.container import Container
from dangerzone.isolation_provider.dummy import Dummy
from dangerzone.updater import (
    BUNDLED_LOG_INDEX,
    EmptyReport,
    InstallationStrategy,
    ReleaseReport,
    releases,
)

from .test_updater import assert_report_equal, default_updater_settings


@fixture
def dummy(mocker: MockerFixture) -> None:
    dummy = mocker.MagicMock(spec=Container)
    dummy.requires_install.return_value = False
    return dummy


@fixture
def content_widget(qtbot: QtBot, mocker: MockerFixture) -> ContentWidget:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()
    dz = DangerzoneGui(mock_app, dummy)
    w = ContentWidget(dz)
    qtbot.addWidget(w)
    return w


def drag_files_event(mocker: MockerFixture, files: List[str]) -> QtGui.QDropEvent:
    ev = mocker.MagicMock(spec=QtGui.QDropEvent)
    ev.accept.return_value = True

    urls = [QtCore.QUrl.fromLocalFile(x) for x in files]
    ev.mimeData.return_value.has_urls.return_value = True
    ev.mimeData.return_value.urls.return_value = urls
    return ev


@fixture
def drag_valid_files_event(
    mocker: MockerFixture, sample_doc: str, sample_pdf: str
) -> QtGui.QDropEvent:
    return drag_files_event(mocker, [sample_doc, sample_pdf])


@fixture
def drag_1_invalid_file_event(
    mocker: MockerFixture, sample_doc: str, tmp_path: pathlib.Path
) -> QtGui.QDropEvent:
    unsupported_file_path = tmp_path / "file.unsupported"
    shutil.copy(sample_doc, unsupported_file_path)
    return drag_files_event(mocker, [str(unsupported_file_path)])


@fixture
def drag_1_invalid_and_2_valid_files_event(
    mocker: MockerFixture, tmp_path: pathlib.Path, sample_doc: str, sample_pdf: str
) -> QtGui.QDropEvent:
    unsupported_file_path = tmp_path / "file.unsupported"
    shutil.copy(sample_doc, unsupported_file_path)
    return drag_files_event(
        mocker, [sample_doc, sample_pdf, str(unsupported_file_path)]
    )


@fixture
def drag_text_event(mocker: MockerFixture) -> QtGui.QDropEvent:
    ev = mocker.MagicMock()
    ev.accept.return_value = True
    ev.mimeData.return_value.has_urls.return_value = False
    return ev


def test_default_menu(
    qtbot: QtBot,
    updater: UpdaterThread,
) -> None:
    """Check that the default menu entries are in order."""
    updater.dangerzone.settings.set("updater_check_all", True)

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

    # Let's pretend we planned to have a update already
    updater.dangerzone.settings.set("updater_remote_log_index", 1000, autosave=True)
    toggle_updates_action.trigger()
    assert not toggle_updates_action.isChecked()
    assert updater.dangerzone.settings.get("updater_check_all") is False
    # We keep the remote log index in case updates are activated back
    # It doesn't mean they will be applied.
    assert updater.dangerzone.settings.get("updater_remote_log_index") is 1000


def test_no_new_release(
    qtbot: QtBot,
    updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that when no new release has been detected, the user is not alerted."""
    # Check that when no update is detected, e.g., due to update cooldown, an empty
    # report is received that does not affect the menu entries.
    curtime = int(time.time())
    updater.dangerzone.settings.set("updater_check_all", True)
    updater.dangerzone.settings.set("updater_errors", 9)
    updater.dangerzone.settings.set("updater_last_check", curtime)
    updater.dangerzone.settings.set("updater_remote_log_index", 0)

    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_errors"] = 0  # errors must be cleared
    expected_settings["updater_last_check"] = curtime
    expected_settings["updater_remote_log_index"] = 0

    window = MainWindow(updater.dangerzone)
    window.register_update_handler(updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")

    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(updater.finished):
        updater.start()

    # Check that the callback function gets an empty report.
    handle_updates_spy.assert_called_once()
    assert_report_equal(handle_updates_spy.call_args.args[0], EmptyReport())

    # Check that the menu entries remain exactly the same.
    menu_actions_after = window.hamburger_button.menu().actions()
    assert menu_actions_before == menu_actions_after

    # Check that any previous update errors are cleared.
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings


def test_new_release_is_detected(
    qtbot: QtBot,
    qt_updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that a newly detected version leads to a notification to the user."""

    qt_updater.dangerzone.settings.set("updater_check_all", True)
    qt_updater.dangerzone.settings.set("updater_last_check", 0)
    qt_updater.dangerzone.settings.set("updater_errors", 9)
    qt_updater.dangerzone.settings.set("updater_remote_log_index", 0)

    # Make requests.get().json() return the following dictionary.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = releases.requests.get
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    window = MainWindow(qt_updater.dangerzone)
    window.register_update_handler(qt_updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")
    load_svg_spy = mocker.spy(main_window_module, "load_svg_image")

    # Let's pretend we have a new container image out by bumping the remote logindex
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 1000000000000000000, None],
    )
    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(qt_updater.finished):
        qt_updater.start()

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    handle_updates_spy.assert_called_once()
    assert_report_equal(
        handle_updates_spy.call_args.args[0],
        ReleaseReport("99.9.9", "<p>changelog</p>", container_image_bump=True),
    )

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_last_check"] = qt_updater.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_latest_version"] = "99.9.9"
    expected_settings["updater_latest_changelog"] = "<p>changelog</p>"
    expected_settings["updater_errors"] = 0
    expected_settings["updater_remote_log_index"] = 1000000000000000000
    assert qt_updater.dangerzone.settings.get_updater_settings() == expected_settings

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
        dialog = qt_updater.dangerzone.app.activeWindow()

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

        # Extend the "What's New" section and ensure that the dialog's height
        # increases.
        with qtbot.waitSignal(collapsible_box.toggle_animation.finished):
            collapsible_box.toggle_button.click()

        # FIXME:
        # assert dialog.sizeHint().height() > height_initial
        # assert dialog.sizeHint().width() == width_initial

        # Collapse the "What's New" section, and ensure that the dialog's height gets
        # back to the original value.
        with qtbot.waitSignal(collapsible_box.toggle_animation.finished):
            collapsible_box.toggle_button.click()

        assert dialog.sizeHint().height() == height_initial
        assert dialog.sizeHint().width() == width_initial

        dialog.close()

    QtCore.QTimer.singleShot(500, check_dialog)
    success_action.trigger()

    # FIXME: We should check the content of the dialog here.


def test_update_error(
    qtbot: QtBot,
    qt_updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that an error during an update check leads to a notification to the user."""
    # Test 1 - Check that the first error does not notify the user.
    qt_updater.dangerzone.settings.set("updater_check_all", True)
    qt_updater.dangerzone.settings.set("updater_last_check", 0)
    qt_updater.dangerzone.settings.set("updater_errors", 0)

    # Make requests.get() return an error
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = releases.requests.get
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]

    window = MainWindow(qt_updater.dangerzone)
    window.register_update_handler(qt_updater.finished)
    handle_updates_spy = mocker.spy(window, "handle_updates")
    load_svg_spy = mocker.spy(main_window_module, "load_svg_image")

    menu_actions_before = window.hamburger_button.menu().actions()

    with qtbot.waitSignal(qt_updater.finished):
        qt_updater.start()

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    handle_updates_spy.assert_called_once()
    assert "failed" in handle_updates_spy.call_args.args[0].error

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_last_check"] = qt_updater.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_errors"] += 1
    assert qt_updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that the hamburger icon has not changed.
    assert load_svg_spy.call_count == 0

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 2 - Check that the second error does not notify the user either.
    qt_updater.dangerzone.settings.set("updater_last_check", 0)
    with qtbot.waitSignal(qt_updater.finished):
        qt_updater.start()

    assert load_svg_spy.call_count == 0

    # Check that the settings have been updated properly.
    expected_settings["updater_errors"] += 1
    expected_settings["updater_last_check"] = qt_updater.dangerzone.settings.get(
        "updater_last_check"
    )
    assert qt_updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 3 - Check that a third error shows a new menu entry.
    qt_updater.dangerzone.settings.set("updater_last_check", 0)
    with qtbot.waitSignal(qt_updater.finished):
        qt_updater.start()

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
        dialog = qt_updater.dangerzone.app.activeWindow()

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
# Document Selection tests
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
    assert file_dialog_mock.exec.call_count == 2
    assert file_dialog_mock.selectedFiles.call_count == 2

    # Then the final document should be only the second one
    docs = [
        doc.input_filename
        for doc in content_widget.dangerzone.get_unconverted_documents()
    ]
    assert len(docs) == 1
    assert docs[0] == str(tmp_sample_doc)


def test_drop_valid_documents(
    content_widget: ContentWidget,
    drag_valid_files_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.waitSignal(
        content_widget.doc_selection_wrapper.documents_selected,
        check_params_cb=lambda x: len(x) == 2 and isinstance(x[0], Document),
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_valid_files_event)


def test_drop_text(
    content_widget: ContentWidget,
    drag_text_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.assertNotEmitted(
        content_widget.doc_selection_wrapper.documents_selected
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_text_event)


def test_drop_1_invalid_doc(
    content_widget: ContentWidget,
    drag_1_invalid_file_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.assertNotEmitted(
        content_widget.doc_selection_wrapper.documents_selected
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_1_invalid_file_event)


def test_drop_1_invalid_2_valid_documents(
    content_widget: ContentWidget,
    drag_1_invalid_and_2_valid_files_event: QtGui.QDropEvent,
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
) -> None:
    # If we accept to continue
    monkeypatch.setattr(
        content_widget.doc_selection_wrapper, "prompt_continue_without", lambda x: True
    )

    # Then the 2 valid docs will be selected
    with qtbot.waitSignal(
        content_widget.doc_selection_wrapper.documents_selected,
        check_params_cb=lambda x: len(x) == 2 and isinstance(x[0], Document),
    ):
        content_widget.doc_selection_wrapper.dropEvent(
            drag_1_invalid_and_2_valid_files_event
        )

    # If we refuse to continue
    monkeypatch.setattr(
        content_widget.doc_selection_wrapper, "prompt_continue_without", lambda x: False
    )

    # Then no docs will be selected
    with qtbot.assertNotEmitted(
        content_widget.doc_selection_wrapper.documents_selected,
    ):
        content_widget.doc_selection_wrapper.dropEvent(
            drag_1_invalid_and_2_valid_files_event
        )


def test_not_available_container_tech_exception(
    qtbot: QtBot, mocker: MockerFixture
) -> None:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = Dummy()
    fn = mocker.patch.object(dummy, "is_available")
    fn.side_effect = errors.NotAvailableContainerTechException(
        "podman", "podman image ls logs"
    )

    dz = DangerzoneGui(mock_app, dummy)
    widget = WaitingWidgetContainer(dz)
    qtbot.addWidget(widget)

    # Assert that the error is displayed in the GUI
    if platform.system() in ["Darwin", "Windows"]:
        assert "Dangerzone requires Docker Desktop" in widget.label.text()
    else:
        assert "Podman is installed but cannot run properly" in widget.label.text()

    assert "podman image ls logs" in widget.traceback.toPlainText()


def test_no_container_tech_exception(qtbot: QtBot, mocker: MockerFixture) -> None:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()

    # Raise
    dummy.is_available.side_effect = errors.NoContainerTechException("podman")

    dz = DangerzoneGui(mock_app, dummy)
    widget = WaitingWidgetContainer(dz)
    qtbot.addWidget(widget)

    # Assert that the error is displayed in the GUI
    if platform.system() in ["Darwin", "Windows"]:
        assert "Dangerzone requires Docker Desktop" in widget.label.text()
    else:
        assert "Dangerzone requires Podman" in widget.label.text()


def test_installation_failure_exception(qtbot: QtBot, mocker: MockerFixture) -> None:
    """Ensures that if an exception is raised during image installation,
    it is shown in the GUI.
    """
    # Setup install to raise an exception
    mock_app = mocker.MagicMock()

    mocker.patch(
        "dangerzone.gui.main_window.get_installation_strategy",
        return_value=InstallationStrategy.INSTALL_LOCAL_CONTAINER,
    )
    dummy = mocker.MagicMock(spec=Container)
    installer = mocker.patch(
        "dangerzone.gui.main_window.apply_installation_strategy",
        side_effect=RuntimeError("Error during install"),
    )

    dz = DangerzoneGui(mock_app, dummy)

    # Mock the InstallContainerThread to call the original run method instead of
    # starting a new thread
    mocker.patch.object(InstallContainerThread, "start", InstallContainerThread.run)
    widget = WaitingWidgetContainer(dz)
    qtbot.addWidget(widget)

    assert installer.call_count == 1

    assert "Error during install" in widget.traceback.toPlainText()
    assert "RuntimeError" in widget.traceback.toPlainText()


def test_up_to_date_docker_desktop_does_nothing(
    qtbot: QtBot, mocker: MockerFixture, dummy: MagicMock
) -> None:
    dummy.check_docker_desktop_version.return_value = (True, "1.0.0")

    mock_app = mocker.MagicMock()
    dz = DangerzoneGui(mock_app, dummy)

    window = MainWindow(dz)
    qtbot.addWidget(window)

    menu_actions = window.hamburger_button.menu().actions()
    assert "Docker Desktop should be upgraded" not in [
        a.toolTip() for a in menu_actions
    ]


def test_outdated_docker_desktop_displays_warning(
    qtbot: QtBot, mocker: MockerFixture, dummy: MagicMock
) -> None:
    # Setup install to return False
    mock_app = mocker.MagicMock()
    dummy.check_docker_desktop_version.return_value = (False, "1.0.0")

    dz = DangerzoneGui(mock_app, dummy)

    load_svg_spy = mocker.spy(main_window_module, "load_svg_image")

    window = MainWindow(dz)
    qtbot.addWidget(window)

    menu_actions = window.hamburger_button.menu().actions()
    assert menu_actions[0].toolTip() == "Docker Desktop should be upgraded"

    # Check that the hamburger icon has changed with the expected SVG image.
    assert load_svg_spy.call_count == 4
    assert (
        load_svg_spy.call_args_list[2].args[0] == "hamburger_menu_update_dot_error.svg"
    )

    alert_spy = mocker.spy(window.alert, "launch")

    # Clicking the menu item should open a warning message
    def _check_alert_displayed() -> None:
        alert_spy.assert_any_call()
        if window.alert:
            window.alert.close()

    QtCore.QTimer.singleShot(0, _check_alert_displayed)
    menu_actions[0].trigger()
