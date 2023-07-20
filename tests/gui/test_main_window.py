from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui import MainWindow
from dangerzone.gui import updater as updater_mod
from dangerzone.gui.updater import UpdateReport, UpdaterThread
from dangerzone.util import get_version

from . import qt_updater, updater
from .test_updater import default_updater_settings


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
