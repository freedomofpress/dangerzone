from pytest import MonkeyPatch, fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui import MainWindow
from dangerzone.gui import updater as updater_mod
from dangerzone.gui.main_window import *
from dangerzone.gui.updater import UpdateReport, UpdaterThread
from dangerzone.util import get_version

from .. import sample_doc, sample_pdf
from . import qt_updater, updater
from .test_updater import default_updater_settings

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets


##
## Widget Fixtures
##


@fixture
def content_widget(qtbot: QtBot, mocker: MockerFixture) -> QtWidgets.QWidget:
    # Setup
    mock_app = mocker.MagicMock()
    dummy = mocker.MagicMock()
    dz = DangerzoneGui(mock_app, dummy)
    w = ContentWidget(dz)
    qtbot.addWidget(w)
    return w


def test_qt(
    qtbot: QtBot,
    qt_updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    updater = qt_updater
    updater.dangerzone.settings.set("updater_check", True)
    updater.dangerzone.settings.set("updater_last_check", 0)
    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = True

    mock_upstream_info = {"tag_name": f"v{get_version()}", "body": "changelog"}

    # Always assume that we can perform multiple update checks in a row.
    monkeypatch.setattr(updater, "_should_postpone_update_check", lambda: False)

    # Make requests.get().json() return the above dictionary.
    requests_mock = mocker.MagicMock()
    requests_mock().json.return_value = mock_upstream_info
    monkeypatch.setattr(updater_mod.requests, "get", requests_mock)

    window = MainWindow(updater.dangerzone)
    window.register_update_handler(updater.finished)
    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    assert len(window.hamburger_button.menu().actions()) == 3
    expected_settings["updater_last_check"] = updater.dangerzone.settings.get(
        "updater_last_check"
    )
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    mock_upstream_info["tag_name"] = "v99.9.9"
    mock_upstream_info["changelog"] = "changelog"
    expected_settings["updater_latest_version"] = "99.9.9"
    expected_settings["updater_latest_changelog"] = "<p>changelog</p>"

    with qtbot.waitSignal(updater.finished) as blocker:
        updater.start()

    # The separator and install updates button has been added
    assert len(window.hamburger_button.menu().actions()) == 5
    expected_settings["updater_last_check"] = updater.dangerzone.settings.get(
        "updater_last_check"
    )
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # TODO:
    # 1. Test that hamburger icon changes according to the update status.
    # 2. Check that the dialogs for new updates / update errors have the expected
    #    content.
    # 3. Check that a user can toggle updates from the hamburger menu.
    # 4. Check that errors are cleared from the settings, whenever we have a successful
    #    update check.
    # 5. Check that latest version/changelog, as well as update errors, are cached in
    #    the settings


##
## Document Selection tests
##


def test_change_document_button(
    content_widget: ContentWidget,
    qtbot: QtBot,
    mocker: MockerFixture,
    sample_pdf: str,
    sample_doc: str,
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
    file_dialog_mock.selectedFiles.return_value = (sample_doc,)

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
    assert docs[0] == sample_doc
