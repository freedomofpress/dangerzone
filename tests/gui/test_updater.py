import json
import os
import platform
import sys
import time
import typing
from pathlib import Path

import pytest
from PySide6 import QtCore
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone import settings
from dangerzone.gui import MainWindow
from dangerzone.gui import updater as updater_module
from dangerzone.gui.updater import UpdateReport, UpdaterThread
from dangerzone.util import get_version

from ..test_settings import default_settings_0_4_1, save_settings
from . import generate_isolated_updater, qt_updater, updater


def default_updater_settings() -> dict:
    """Get the default updater settings for the current Dangerzone release.

    This function acquires the settings strictly from code, and does not initialize
    the Settings class. This way, we avoid writing any settings to the filesystem.
    """
    return {
        key: val
        for key, val in settings.Settings.generate_default_settings().items()
        if key.startswith("updater_")
    }


def assert_report_equal(report1: UpdateReport, report2: UpdateReport) -> None:
    assert report1.version == report2.version
    assert report1.changelog == report2.changelog
    assert report1.error == report2.error


def test_default_updater_settings(updater: UpdaterThread) -> None:
    """Check that new 0.4.2 installations have the expected updater settings.

    This test is mostly a sanity check.
    """
    assert (
        updater.dangerzone.settings.get_updater_settings() == default_updater_settings()
    )


def test_pre_0_4_2_settings(
    tmp_path: Path, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Check settings of installations prior to 0.4.2.

    Check that installations that have been upgraded from a version < 0.4.2 to >= 0.4.2
    will automatically get the default updater settings, even though they never existed
    in their settings.json file.
    """
    save_settings(tmp_path, default_settings_0_4_1())
    updater = generate_isolated_updater(tmp_path, monkeypatch, mocker)
    assert (
        updater.dangerzone.settings.get_updater_settings() == default_updater_settings()
    )


def test_post_0_4_2_settings(
    tmp_path: Path, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Check settings of installations post-0.4.2.

    Installations from 0.4.2 onwards will have a "updater_latest_version" field in their
    settings. When these installations get upgraded to a newer version, we must make
    sure that this field becomes equal to the new version, so that the user is not
    erroneously prompted to a version they already have.
    """
    # Store the settings of Dangerzone 0.4.2 to the filesystem.
    old_settings = settings.Settings.generate_default_settings()
    old_settings["updater_latest_version"] = "0.4.2"
    save_settings(tmp_path, old_settings)

    # Mimic an upgrade to version 0.4.3, by making Dangerzone report that the current
    # version is 0.4.3.
    expected_settings = default_updater_settings()
    expected_settings["updater_latest_version"] = "0.4.3"
    monkeypatch.setattr(
        settings, "get_version", lambda: expected_settings["updater_latest_version"]
    )

    # Ensure that the Settings class will correct the latest version field to 0.4.3.
    updater = generate_isolated_updater(tmp_path, monkeypatch, mocker)
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Simulate an updater check that found a newer Dangerzone version (e.g., 0.4.4).
    expected_settings["updater_latest_version"] = "0.4.4"
    updater.dangerzone.settings.set(
        "updater_latest_version", expected_settings["updater_latest_version"]
    )
    updater.dangerzone.settings.save()

    # Ensure that the Settings class will leave the "updater_latest_version" field
    # intact the next time we reload the settings.
    updater.dangerzone.settings.load()
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only test")
def test_linux_no_check(updater: UpdaterThread, monkeypatch: MonkeyPatch) -> None:
    """Ensure that Dangerzone on Linux does not make any update check."""
    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = False
    expected_settings["updater_last_check"] = None

    # XXX: Simulate Dangerzone installed via package manager.
    monkeypatch.delattr(sys, "dangerzone_dev")

    assert updater.should_check_for_updates() == False
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings


def test_user_prompts(
    updater: UpdaterThread, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Test prompting users to ask them if they want to enable update checks."""
    # First run
    #
    # When Dangerzone runs for the first time, users should not be asked to enable
    # updates.
    expected_settings = default_updater_settings()
    expected_settings["updater_check"] = None
    expected_settings["updater_last_check"] = 0
    assert updater.should_check_for_updates() == False
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Second run
    #
    # When Dangerzone runs for a second time, users can be prompted to enable update
    # checks. Depending on their answer, we should either enable or disable them.
    mocker.patch("dangerzone.gui.updater.UpdateCheckPrompt")
    prompt_mock = updater_module.UpdateCheckPrompt
    prompt_mock().x_pressed = False

    # Check disabling update checks.
    prompt_mock().launch.return_value = False  # type: ignore [attr-defined]
    expected_settings["updater_check"] = False
    assert updater.should_check_for_updates() == False
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Reset the "updater_check" field and check enabling update checks.
    updater.dangerzone.settings.set("updater_check", None)
    prompt_mock().launch.return_value = True  # type: ignore [attr-defined]
    expected_settings["updater_check"] = True
    assert updater.should_check_for_updates() == True
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings

    # Third run
    #
    # From the third run onwards, users should never be prompted for enabling update
    # checks.
    prompt_mock().side_effect = RuntimeError("Should not be called")  # type: ignore [attr-defined]
    for check in [True, False]:
        updater.dangerzone.settings.set("updater_check", check)
        assert updater.should_check_for_updates() == check


def test_update_checks(
    updater: UpdaterThread, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Test version update checks."""
    # This dictionary will simulate GitHub's response.
    mock_upstream_info = {"tag_name": f"v{get_version()}", "body": "changelog"}

    # Make requests.get().json() return the above dictionary.
    mocker.patch("dangerzone.gui.updater.requests.get")
    requests_mock = updater_module.requests.get
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    # Always assume that we can perform multiple update checks in a row.
    monkeypatch.setattr(updater, "_should_postpone_update_check", lambda: False)

    # Test 1 - Check that the current version triggers no updates.
    report = updater.check_for_updates()
    assert_report_equal(report, UpdateReport())

    # Test 2 - Check that a newer version triggers updates, and that the changelog is
    # rendered from Markdown to HTML.
    mock_upstream_info["tag_name"] = "v99.9.9"
    report = updater.check_for_updates()
    assert_report_equal(
        report, UpdateReport(version="99.9.9", changelog="<p>changelog</p>")
    )

    # Test 3 - Check that HTTP errors are converted to error reports.
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    error_msg = (
        f"Encountered an exception while checking {updater.GH_RELEASE_URL}: failed"
    )
    assert_report_equal(report, UpdateReport(error=error_msg))

    # Test 4 - Check that cached version/changelog info do not trigger an update check.
    updater.dangerzone.settings.set("updater_latest_version", "99.9.9")
    updater.dangerzone.settings.set("updater_latest_changelog", "<p>changelog</p>")

    report = updater.check_for_updates()
    assert_report_equal(
        report, UpdateReport(version="99.9.9", changelog="<p>changelog</p>")
    )


def test_update_checks_cooldown(updater: UpdaterThread, mocker: MockerFixture) -> None:
    """Make sure Dangerzone only checks for updates every X hours"""
    updater.dangerzone.settings.set("updater_check", True)
    updater.dangerzone.settings.set("updater_last_check", 0)

    # Mock some functions before the tests start
    cooldown_spy = mocker.spy(updater, "_should_postpone_update_check")
    timestamp_mock = mocker.patch.object(updater, "_get_now_timestamp")
    mocker.patch("dangerzone.gui.updater.requests.get")
    requests_mock = updater_module.requests.get

    # # Make requests.get().json() return the version info that we want.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    # Test 1: The first time Dangerzone checks for updates, the cooldown period should
    # not stop it. Once we learn about an update, the last check setting should be
    # bumped.
    curtime = int(time.time())
    timestamp_mock.return_value = curtime

    report = updater.check_for_updates()
    assert cooldown_spy.spy_return == False
    assert updater.dangerzone.settings.get("updater_last_check") == curtime
    assert_report_equal(report, UpdateReport("99.9.9", "<p>changelog</p>"))

    # Test 2: Advance the current time by 1 second, and ensure that no update will take
    # place, due to the cooldown period. The last check timestamp should remain the
    # previous one.
    curtime += 1
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]
    updater.dangerzone.settings.set("updater_latest_version", get_version())
    updater.dangerzone.settings.set("updater_latest_changelog", None)

    report = updater.check_for_updates()
    assert cooldown_spy.spy_return == True
    assert updater.dangerzone.settings.get("updater_last_check") == curtime - 1
    assert_report_equal(report, UpdateReport())

    # Test 3: Advance the current time by <cooldown period> seconds. Ensure that
    # Dangerzone checks for updates again, and the last check timestamp gets bumped.
    curtime += updater_module.UPDATE_CHECK_COOLDOWN_SECS
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = None  # type: ignore [attr-defined]

    report = updater.check_for_updates()
    assert cooldown_spy.spy_return == False
    assert updater.dangerzone.settings.get("updater_last_check") == curtime
    assert_report_equal(report, UpdateReport("99.9.9", "<p>changelog</p>"))

    # Test 4: Make Dangerzone check for updates again, but this time, it should
    # encounter an error while doing so. In that case, the last check timestamp
    # should be bumped, so that subsequent checks don't take place.
    updater.dangerzone.settings.set("updater_latest_version", get_version())
    updater.dangerzone.settings.set("updater_latest_changelog", None)

    curtime += updater_module.UPDATE_CHECK_COOLDOWN_SECS
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]

    report = updater.check_for_updates()
    assert cooldown_spy.spy_return == False
    assert updater.dangerzone.settings.get("updater_last_check") == curtime
    error_msg = (
        f"Encountered an exception while checking {updater.GH_RELEASE_URL}: failed"
    )
    assert_report_equal(report, UpdateReport(error=error_msg))


def test_update_errors(
    updater: UpdaterThread, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Test update check errors."""
    # Mock requests.get().
    mocker.patch("dangerzone.gui.updater.requests.get")
    requests_mock = updater_module.requests.get

    # Always assume that we can perform multiple update checks in a row.
    monkeypatch.setattr(updater, "_should_postpone_update_check", lambda: False)

    # Test 1 - Check that request exceptions are being detected as errors.
    requests_mock.side_effect = Exception("bad url")  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None
    assert "bad url" in report.error
    assert "Encountered an exception" in report.error

    # Test 2 - Check that non HTTP 200 responses are detected as errors.
    class MockResponse500:
        status_code = 500

    requests_mock.return_value = MockResponse500()  # type: ignore [attr-defined]
    requests_mock.side_effect = None  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None
    assert "Encountered an HTTP 500 error" in report.error

    # Test 3 - Check that non JSON responses are detected as errors.
    class MockResponseBadJSON:
        status_code = 200

        def json(self) -> dict:
            return json.loads("bad json")

    requests_mock.return_value = MockResponseBadJSON()  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None
    assert "Received a non-JSON response" in report.error

    # Test 4 - Check that missing fields in JSON are detected as errors.
    class MockResponseEmpty:
        status_code = 200

        def json(self) -> dict:
            return {}

    requests_mock.return_value = MockResponseEmpty()  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None
    assert "Missing required fields in JSON" in report.error

    # Test 5 - Check invalid versions are reported
    class MockResponseBadVersion:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "vbad_version", "body": "changelog"}

    requests_mock.return_value = MockResponseBadVersion()  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None
    assert "Invalid version" in report.error

    # Test 6 - Check invalid markdown is reported
    class MockResponseBadMarkdown:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": ["bad", "markdown"]}

    requests_mock.return_value = MockResponseBadMarkdown()  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert report.error is not None

    # Test 7 - Check that a valid response passes.
    class MockResponseValid:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": "changelog"}

    requests_mock.return_value = MockResponseValid()  # type: ignore [attr-defined]
    report = updater.check_for_updates()
    assert_report_equal(report, UpdateReport("99.9.9", "<p>changelog</p>"))


def test_update_check_prompt(
    qtbot: QtBot,
    qt_updater: UpdaterThread,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test that the prompt to enable update checks works properly."""
    # Force Dangerzone to check immediately for updates
    qt_updater.dangerzone.settings.set("updater_last_check", 0)

    # Test 1 - Check that on the second run of Dangerzone, the user is prompted to
    # choose if they want to enable update checks.
    def check_button_labels() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        assert dialog.ok_button.text() == "Check Automatically"  # type: ignore [attr-defined]
        assert dialog.cancel_button.text() == "Don't Check"  # type: ignore [attr-defined]
        dialog.ok_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, check_button_labels)
    res = qt_updater.should_check_for_updates()

    assert res == True

    # Test 2 - Check that when the user chooses to enable update checks, we
    # store that decision in the settings.
    qt_updater.check = None

    def click_ok() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.ok_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, click_ok)
    res = qt_updater.should_check_for_updates()

    assert res == True
    assert qt_updater.check == True

    # Test 3 - Same as the previous test, but check that clicking on cancel stores the
    # opposite decision.
    qt_updater.check = None

    def click_cancel() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.cancel_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, click_cancel)
    res = qt_updater.should_check_for_updates()

    assert res == False
    assert qt_updater.check == False

    # Test 4 - Same as the previous test, but check that clicking on "X" does not store
    # any decision.
    qt_updater.check = None

    def click_x() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.close()

    QtCore.QTimer.singleShot(500, click_x)
    res = qt_updater.should_check_for_updates()

    assert res == False
    assert qt_updater.check == None
