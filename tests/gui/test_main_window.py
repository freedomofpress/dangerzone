import os
import pathlib
import platform
import shutil
import time
import typing
from typing import List
from unittest.mock import MagicMock

from pytest import MonkeyPatch, fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

from dangerzone import errors, settings, startup
from dangerzone.document import Document
from dangerzone.gui import MainWindow
from dangerzone.gui import main_window as main_window_module
from dangerzone.gui import updater as updater_module
from dangerzone.gui.logic import DangerzoneGui

# import Pyside related objects from here to avoid duplicating import logic.
from dangerzone.gui.main_window import (
    ConversionWidget,
    QtCore,
    QtGui,
    # WaitingWidgetContainer,
)
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
def content_widget(qtbot: QtBot, mocker: MockerFixture) -> ConversionWidget:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()
    dz = DangerzoneGui(mock_app, dummy)
    w = ConversionWidget(dz)
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


def create_main_window(
    qtbot: QtBot, mocker: MockerFixture, tmp_path: pathlib.Path
) -> MainWindow:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock(spec=Dummy)
    dz = DangerzoneGui(mock_app, dummy)

    window = MainWindow(dz)
    qtbot.addWidget(window)
    return window


@fixture
def window(qtbot: QtBot, mocker: MockerFixture, tmp_path: pathlib.Path) -> MainWindow:
    return create_main_window(qtbot, mocker, tmp_path)


def test_default_menu(
    qtbot: QtBot, mocker: MockerFixture, tmp_path: pathlib.Path
) -> None:
    """Check that the default menu entries are in order."""
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings.Settings().set("updater_check_all", True)
    window = create_main_window(qtbot, mocker, tmp_path)

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
    window.dangerzone.settings.set("updater_remote_log_index", 1000, autosave=True)
    toggle_updates_action.trigger()
    assert not toggle_updates_action.isChecked()
    assert window.dangerzone.settings.get("updater_check_all") is False
    # We keep the remote log index in case updates are activated back
    # It doesn't mean they will be applied.
    assert window.dangerzone.settings.get("updater_remote_log_index") is 1000


def test_no_new_release(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    window: MainWindow,
) -> None:
    """Test that when no new release has been detected, the user is not alerted."""
    for task in window.startup_thread.tasks:
        should_skip = not isinstance(task, startup.UpdateCheckTask)
        mocker.patch.object(task, "should_skip", return_value=should_skip)

    # Check that when no update is detected, e.g., due to update cooldown, an empty
    # report is received that does not affect the menu entries.
    curtime = int(time.time())
    window.dangerzone.settings.set("updater_check_all", True)
    window.dangerzone.settings.set("updater_errors", 9)
    window.dangerzone.settings.set("updater_last_check", curtime)
    window.dangerzone.settings.set("updater_remote_log_index", 0)

    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_errors"] = 0  # errors must be cleared
    expected_settings["updater_last_check"] = curtime
    expected_settings["updater_remote_log_index"] = 0

    menu_actions_before = window.hamburger_button.menu().actions()
    check_for_updates_spy = mocker.spy(releases, "check_for_updates")
    window.startup_thread.start()
    window.startup_thread.wait()

    def assertions():
        # Check that the callback function gets an empty report.
        assert_report_equal(check_for_updates_spy.spy_return, EmptyReport())

        # Check that the menu entries remain exactly the same.
        menu_actions_after = window.hamburger_button.menu().actions()
        assert menu_actions_before == menu_actions_after

        # Check that any previous update errors are cleared.
        assert window.dangerzone.settings.get_updater_settings() == expected_settings

    qtbot.waitUntil(assertions)


def test_new_release_is_detected(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    window: MainWindow,
) -> None:
    """Test that a newly detected version leads to a notification to the user."""
    for task in window.startup_thread.tasks:
        should_skip = not isinstance(task, startup.UpdateCheckTask)
        mocker.patch.object(task, "should_skip", return_value=should_skip)

    window.dangerzone.settings.set("updater_check_all", True)
    window.dangerzone.settings.set("updater_last_check", 0)
    window.dangerzone.settings.set("updater_errors", 9)
    window.dangerzone.settings.set("updater_remote_log_index", 0)

    # Make requests.get().json() return the following dictionary.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = releases.requests.get
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    load_svg_spy = mocker.spy(main_window_module, "load_svg_image")
    handle_app_update_available_spy = mocker.spy(window, "handle_app_update_available")

    # Let's pretend we have a new container image out by bumping the remote logindex
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 1000000000000000000, None],
    )
    menu_actions_before = window.hamburger_button.menu().actions()
    check_for_updates_spy = mocker.spy(releases, "check_for_updates")

    window.startup_thread.start()
    window.startup_thread.wait()

    qtbot.waitUntil(handle_app_update_available_spy.assert_called_once)

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    assert_report_equal(
        check_for_updates_spy.spy_return,
        ReleaseReport("99.9.9", "<p>changelog</p>", container_image_bump=True),
    )

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_last_check"] = window.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_latest_version"] = "99.9.9"
    expected_settings["updater_latest_changelog"] = "<p>changelog</p>"
    expected_settings["updater_errors"] = 0
    expected_settings["updater_remote_log_index"] = 1000000000000000000
    assert window.dangerzone.settings.get_updater_settings() == expected_settings

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
        dialog = QtWidgets.QApplication.activeWindow()

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

        assert dialog.sizeHint().height() > height_initial
        assert dialog.sizeHint().width() == width_initial

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
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    window: MainWindow,
) -> None:
    """Test that an error during an update check leads to a notification to the user."""
    for task in window.startup_thread.tasks:
        should_skip = not isinstance(task, startup.UpdateCheckTask)
        mocker.patch.object(task, "should_skip", return_value=should_skip)

    # Test 1 - Check that the first error does not notify the user.
    window.dangerzone.settings.set("updater_check_all", True)
    window.dangerzone.settings.set("updater_last_check", 0)
    window.dangerzone.settings.set("updater_errors", 0)

    # Make requests.get() return an error
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = releases.requests.get
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]

    handle_update_check_failed_spy = mocker.spy(window, "handle_update_check_failed")
    load_svg_spy = mocker.spy(main_window_module, "load_svg_image")

    menu_actions_before = window.hamburger_button.menu().actions()
    check_for_updates_spy = mocker.spy(releases, "check_for_updates")
    window.startup_thread.start()
    window.startup_thread.wait()

    qtbot.waitUntil(handle_update_check_failed_spy.assert_called_once)

    menu_actions_after = window.hamburger_button.menu().actions()

    # Check that the callback function gets an update report.
    handle_update_check_failed_spy.assert_called_once()
    assert "failed" in handle_update_check_failed_spy.call_args.args[0]

    # Check that the settings have been updated properly.
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = True
    expected_settings["updater_last_check"] = window.dangerzone.settings.get(
        "updater_last_check"
    )
    expected_settings["updater_errors"] += 1
    assert window.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that the hamburger icon has not changed.
    assert load_svg_spy.call_count == 0

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 2 - Check that the second error does not notify the user either.
    handle_update_check_failed_spy.reset_mock()
    window.dangerzone.settings.set("updater_last_check", 0)
    window.startup_thread.start()
    window.startup_thread.wait()

    qtbot.waitUntil(handle_update_check_failed_spy.assert_called_once)

    assert load_svg_spy.call_count == 0

    # Check that the settings have been updated properly.
    expected_settings["updater_errors"] += 1
    expected_settings["updater_last_check"] = window.dangerzone.settings.get(
        "updater_last_check"
    )
    assert window.dangerzone.settings.get_updater_settings() == expected_settings

    # Check that no menu entries have been added.
    assert menu_actions_before == menu_actions_after

    # Test 3 - Check that a third error shows a new menu entry.
    handle_update_check_failed_spy.reset_mock()
    window.dangerzone.settings.set("updater_last_check", 0)
    window.startup_thread.start()
    window.startup_thread.wait()
    qtbot.waitUntil(handle_update_check_failed_spy.assert_called_once)

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
        dialog = QtWidgets.QApplication.activeWindow()

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
    content_widget: ConversionWidget,
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
    content_widget: ConversionWidget,
    drag_valid_files_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.waitSignal(
        content_widget.doc_selection_wrapper.documents_selected,
        check_params_cb=lambda x: len(x) == 2 and isinstance(x[0], Document),
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_valid_files_event)


def test_drop_text(
    content_widget: ConversionWidget,
    drag_text_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.assertNotEmitted(
        content_widget.doc_selection_wrapper.documents_selected
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_text_event)


def test_drop_1_invalid_doc(
    content_widget: ConversionWidget,
    drag_1_invalid_file_event: QtGui.QDropEvent,
    qtbot: QtBot,
) -> None:
    with qtbot.assertNotEmitted(
        content_widget.doc_selection_wrapper.documents_selected
    ):
        content_widget.doc_selection_wrapper.dropEvent(drag_1_invalid_file_event)


def test_drop_1_invalid_2_valid_documents(
    content_widget: ConversionWidget,
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


def test_installation_failure_exception(
    qtbot: QtBot,
    mocker: MockerFixture,
    window: MainWindow,
) -> None:
    """Ensures that if an exception is raised during image installation,
    it is shown in the GUI.
    """
    installer = mocker.patch(
        "dangerzone.updater.installer.install",
        side_effect=RuntimeError("Error during install"),
    )
    for task in window.startup_thread.tasks:
        should_skip = not isinstance(task, startup.ContainerInstallTask)
        mocker.patch.object(task, "should_skip", return_value=should_skip)

    handle_container_install_failed_spy = mocker.spy(
        window.log_window, "handle_task_container_install_failed"
    )
    window.startup_thread.start()
    window.startup_thread.wait()
    qtbot.waitUntil(handle_container_install_failed_spy.assert_called_once)

    assert installer.call_count == 1
    assert window.status_bar.styleSheet() == "color: red; font-weight: bold"
    assert window.status_bar.message.text() == "Startup failed"
    assert window.log_window.label.text() == "Installing container sandbox… failed"
    assert "Error during install" in window.log_window.traceback_widget.toPlainText()


def test_close_event_stops_podman_machine(
    qtbot: QtBot,
    mocker: MockerFixture,
    dummy: MagicMock,
    window: MainWindow,
) -> None:
    """Test that the Podman machine is stopped on closeEvent."""
    # Mock the platform to be Windows or Darwin
    mocker.patch("platform.system", return_value="Windows")
    mock_podman_machine_manager = mocker.patch(
        "dangerzone.gui.main_window.PodmanMachineManager"
    )
    # Mock the PodmanMachineManager
    mocker.patch("platform.system", return_value="Windows")
    # Mock the alert so that we can close the window
    mock_alert = mocker.patch("dangerzone.gui.main_window.Alert")

    window.close()

    mock_podman_machine_manager().stop.assert_called_once()
    mock_alert.assert_called_once()


def test_user_prompts(qtbot: QtBot, window: MainWindow, mocker: MockerFixture) -> None:
    """Test prompting users to ask them if they want to enable update checks."""
    # First run
    #
    # When Dangerzone runs for the first time, users should not be asked to enable
    # updates.
    for task in window.startup_thread.tasks:
        if not isinstance(task, startup.UpdateCheckTask):
            mocker.patch.object(task, "should_skip", return_value=True)

    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = None
    expected_settings["updater_last_check"] = 0

    window.startup_thread.start()
    window.startup_thread.wait()

    assert window.dangerzone.settings.get_updater_settings() == expected_settings

    # Second run
    #
    # When Dangerzone runs for a second time, users can be prompted to enable update
    # checks. Depending on their answer, we should either enable or disable them.
    prompt_mock = mocker.patch("dangerzone.gui.updater.UpdateCheckPrompt")
    prompt_mock().x_pressed = False

    # Check disabling update checks.
    prompt_mock().launch.return_value = False  # type: ignore [attr-defined]
    expected_settings["updater_check_all"] = False
    handle_needs_user_input_spy = mocker.spy(window, "handle_needs_user_input")

    window.startup_thread.start()
    window.startup_thread.wait()

    qtbot.waitUntil(handle_needs_user_input_spy.assert_called_once)
    assert window.dangerzone.settings.get_updater_settings() == expected_settings

    # Reset the "updater_check_all" field and check enabling update checks.
    window.dangerzone.settings.set("updater_check_all", None)
    prompt_mock().launch.return_value = True  # type: ignore [attr-defined]
    expected_settings["updater_check_all"] = True

    handle_needs_user_input_spy.reset_mock()
    window.startup_thread.start()
    window.startup_thread.wait()

    qtbot.waitUntil(handle_needs_user_input_spy.assert_called_once)
    assert window.dangerzone.settings.get_updater_settings() == expected_settings

    # Third run
    #
    # From the third run onwards, users should never be prompted for enabling update
    # checks.
    prompt_mock().side_effect = RuntimeError("Should not be called")  # type: ignore [attr-defined]
    for check in [True, False]:
        window.dangerzone.settings.set("updater_check_all", check)
        assert releases.should_check_for_updates(window.dangerzone.settings) == check
