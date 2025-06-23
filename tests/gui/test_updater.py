import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, Union

import pytest
from PySide6 import QtCore
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone import settings
from dangerzone.gui import updater as updater_module
from dangerzone.gui.updater import UpdaterThread
from dangerzone.updater import releases
from dangerzone.updater.releases import (
    EmptyReport,
    ErrorReport,
    ReleaseReport,
)
from dangerzone.util import get_version

from ..test_settings import default_settings_0_4_1, save_settings
from .conftest import generate_isolated_updater


def default_updater_settings() -> Dict[str, Any]:
    """Get the default updater settings for the current Dangerzone release.

    This function acquires the settings strictly from code, and does not initialize
    the Settings class. This way, we avoid writing any settings to the filesystem.
    """
    return {
        key: val
        for key, val in settings.Settings.generate_default_settings().items()
        if key.startswith("updater_")
    }


def assert_report_equal(
    report1: Union[ReleaseReport, EmptyReport, ErrorReport],
    report2: Union[ReleaseReport, EmptyReport, ErrorReport],
) -> None:
    assert type(report1) == type(report2)
    # Python dataclasses give us the __eq__ comparison for free
    assert report1.__eq__(report2)


def test_default_updater_settings(updater: UpdaterThread) -> None:
    """Check that new 0.4.2 installations have the expected updater settings.

    This test is mostly a sanity check.
    """
    assert (
        updater.dangerzone.settings.get_updater_settings() == default_updater_settings()
    )


def test_pre_0_4_2_settings(tmp_path: Path, mocker: MockerFixture) -> None:
    """Check settings of installations prior to 0.4.2.

    Check that installations that have been upgraded from a version < 0.4.2 to >= 0.4.2
    will automatically get the default updater settings, even though they never existed
    in their settings.json file.
    """
    save_settings(tmp_path, default_settings_0_4_1())
    updater = generate_isolated_updater(tmp_path, mocker, mock_app=True)
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
    monkeypatch.setattr(settings, "get_version", lambda: "0.4.3")

    # Ensure that the Settings class will correct the latest version field to 0.4.3.
    updater = generate_isolated_updater(tmp_path, mocker, mock_app=True)
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
    expected_settings["updater_check_all"] = False
    expected_settings["updater_last_check"] = None

    # XXX: Simulate Dangerzone installed via package manager.
    monkeypatch.delattr(sys, "dangerzone_dev")

    assert updater.should_check_for_updates() is False
    assert updater.dangerzone.settings.get_updater_settings() == expected_settings


def test_user_prompts(updater: UpdaterThread, mocker: MockerFixture) -> None:
    """Test prompting users to ask them if they want to enable update checks."""
    settings = updater.dangerzone.settings
    # First run
    #
    # When Dangerzone runs for the first time, users should not be asked to enable
    # updates.
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = None
    expected_settings["updater_last_check"] = 0
    assert updater.should_check_for_updates() is False
    assert settings.get_updater_settings() == expected_settings

    # Second run
    #
    # When Dangerzone runs for a second time, users can be prompted to enable update
    # checks. Depending on their answer, we should either enable or disable them.
    mocker.patch("dangerzone.gui.updater.UpdateCheckPrompt")
    prompt_mock = updater_module.UpdateCheckPrompt
    prompt_mock().x_pressed = False

    # Check disabling update checks.
    prompt_mock().launch.return_value = False  # type: ignore [attr-defined]
    expected_settings["updater_check_all"] = False
    assert updater.should_check_for_updates() is False
    assert settings.get_updater_settings() == expected_settings

    # Reset the "updater_check_all" field and check enabling update checks.
    settings.set("updater_check_all", None)
    prompt_mock().launch.return_value = True  # type: ignore [attr-defined]
    expected_settings["updater_check_all"] = True
    assert updater.should_check_for_updates() is True
    assert settings.get_updater_settings() == expected_settings

    # Third run
    #
    # From the third run onwards, users should never be prompted for enabling update
    # checks.
    prompt_mock().side_effect = RuntimeError("Should not be called")  # type: ignore [attr-defined]
    for check in [True, False]:
        settings.set("updater_check_all", check)
        assert updater.should_check_for_updates() == check


def test_update_checks(
    updater: UpdaterThread, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Test version update checks."""
    settings = updater.dangerzone.settings
    # This dictionary will simulate GitHub's response.
    mock_upstream_info = {"tag_name": f"v{get_version()}", "body": "changelog"}

    # Make requests.get().json() return the above dictionary.
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = updater_module.releases.requests.get
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 0, None],
    )

    # Always assume that we can perform multiple update checks in a row.
    mocker.patch(
        "dangerzone.updater.releases._should_postpone_update_check", return_value=False
    )

    # Test 1 - Check that the current version triggers no updates.
    report = releases.check_for_updates(settings)
    assert_report_equal(report, EmptyReport())

    # Test 2 - Check that a newer version triggers updates, and that the changelog is
    # rendered from Markdown to HTML.
    mock_upstream_info["tag_name"] = "v99.9.9"
    report = releases.check_for_updates(settings)
    assert_report_equal(
        report, ReleaseReport(version="99.9.9", changelog="<p>changelog</p>")
    )

    # Test 3 - Check that HTTP errors are converted to error reports.
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    error_msg = f"Encountered an exception while checking {updater_module.releases.GH_RELEASE_URL}: failed"
    assert_report_equal(report, ErrorReport(error=error_msg))

    # Test 4 - Check that cached version/changelog info do not trigger an update check.
    settings.set("updater_latest_version", "99.9.9")
    settings.set("updater_latest_changelog", "<p>changelog</p>")

    report = releases.check_for_updates(settings)
    assert_report_equal(
        report, ReleaseReport(version="99.9.9", changelog="<p>changelog</p>")
    )


def test_update_checks_cooldown(updater: UpdaterThread, mocker: MockerFixture) -> None:
    """Make sure Dangerzone only checks for updates every X hours"""
    settings = updater.dangerzone.settings

    settings.set("updater_check_all", True)
    settings.set("updater_last_check", 0)

    # Mock some functions before the tests start
    cooldown_spy = mocker.spy(updater_module.releases, "_should_postpone_update_check")
    timestamp_mock = mocker.patch.object(updater_module.releases, "_get_now_timestamp")
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = updater_module.releases.requests.get

    # Mock the response of the container updater check
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 0, None],
    )

    # # Make requests.get().json() return the version info that we want.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    requests_mock().status_code = 200  # type: ignore [call-arg]
    requests_mock().json.return_value = mock_upstream_info  # type: ignore [attr-defined, call-arg]

    # Test 1: The first time Dangerzone checks for updates, the cooldown period should
    # not stop it. Once we learn about an update, the last check setting should be
    # bumped.
    curtime = int(time.time())
    timestamp_mock.return_value = curtime

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is False
    assert settings.get("updater_last_check") == curtime
    assert_report_equal(report, ReleaseReport("99.9.9", "<p>changelog</p>"))

    # Test 2: Advance the current time by 1 second, and ensure that no update will take
    # place, due to the cooldown period. The last check timestamp should remain the
    # previous one.
    curtime += 1
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = Exception("failed")  # type: ignore [attr-defined]
    settings.set("updater_latest_version", get_version())
    settings.set("updater_latest_changelog", None)

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is True
    assert settings.get("updater_last_check") == curtime - 1  # type: ignore [unreachable]
    assert_report_equal(report, EmptyReport())

    # Test 3: Advance the current time by <cooldown period> seconds. Ensure that
    # Dangerzone checks for updates again, and the last check timestamp gets bumped.
    curtime += updater_module.releases.UPDATE_CHECK_COOLDOWN_SECS
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = None

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is False
    assert settings.get("updater_last_check") == curtime
    assert_report_equal(report, ReleaseReport("99.9.9", "<p>changelog</p>"))

    # Test 4: Make Dangerzone check for updates again, but this time, it should
    # encounter an error while doing so. In that case, the last check timestamp
    # should be bumped, so that subsequent checks don't take place.
    settings.set("updater_latest_version", get_version())
    settings.set("updater_latest_changelog", None)

    curtime += updater_module.releases.UPDATE_CHECK_COOLDOWN_SECS
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = Exception("failed")

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is False
    assert settings.get("updater_last_check") == curtime
    error_msg = f"Encountered an exception while checking {updater_module.releases.GH_RELEASE_URL}: failed"
    assert_report_equal(report, ErrorReport(error=error_msg))


def test_update_errors(
    updater: UpdaterThread, monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """Test update check errors."""
    settings = updater.dangerzone.settings
    # Always assume that we can perform multiple update checks in a row.
    monkeypatch.setattr(releases, "_should_postpone_update_check", lambda _: False)
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 0, None],
    )

    # Mock requests.get().
    mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock = releases.requests.get

    # Test 1 - Check that request exceptions are being detected as errors.
    requests_mock.side_effect = Exception("bad url")  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "bad url" in report.error
    assert "Encountered an exception" in report.error

    # Test 2 - Check that non HTTP 200 responses are detected as errors.
    class MockResponse500:
        status_code = 500

    requests_mock.return_value = MockResponse500()  # type: ignore [attr-defined]
    requests_mock.side_effect = None  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Encountered an HTTP 500 error" in report.error

    # Test 3 - Check that non JSON responses are detected as errors.
    class MockResponseBadJSON:
        status_code = 200

        def json(self) -> dict:
            return json.loads("bad json")

    requests_mock.return_value = MockResponseBadJSON()  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Received a non-JSON response" in report.error

    # Test 4 - Check that missing fields in JSON are detected as errors.
    class MockResponseEmpty:
        status_code = 200

        def json(self) -> dict:
            return {}

    requests_mock.return_value = MockResponseEmpty()  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Missing required fields in JSON" in report.error

    # Test 5 - Check invalid versions are reported
    class MockResponseBadVersion:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "vbad_version", "body": "changelog"}

    requests_mock.return_value = MockResponseBadVersion()  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Invalid version" in report.error

    # Test 6 - Check invalid markdown is reported
    class MockResponseBadMarkdown:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": ["bad", "markdown"]}

    requests_mock.return_value = MockResponseBadMarkdown()  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None

    # Test 7 - Check that a valid response passes.
    class MockResponseValid:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": "changelog"}

    requests_mock.return_value = MockResponseValid()  # type: ignore [attr-defined]
    report = releases.check_for_updates(settings)
    assert_report_equal(report, ReleaseReport("99.9.9", "<p>changelog</p>"))


def test_update_check_prompt(
    qtbot: QtBot, qt_updater: UpdaterThread, mocker: MockerFixture
) -> None:
    """Test that the prompt to enable update checks works properly."""
    # Force Dangerzone to check immediately for updates
    settings = qt_updater.dangerzone.settings
    settings.set("updater_last_check", 0)

    # Test 1 - Check that on the second run of Dangerzone, the user is prompted to
    # choose if they want to enable update checks.
    def check_button_labels() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        assert dialog.ok_button.text() == updater_module.OK_TEXT  # type: ignore [attr-defined]
        assert dialog.cancel_button.text() == updater_module.CANCEL_TEXT  # type: ignore [attr-defined]
        dialog.ok_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, check_button_labels)
    mocker.patch(
        "dangerzone.updater.releases._should_postpone_update_check", return_value=False
    )
    assert qt_updater.should_check_for_updates()

    # Test 2 - Check that when the user chooses to enable update checks, we
    # store that decision in the settings.
    settings.set("updater_check_all", None, autosave=True)

    def click_ok() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.ok_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, click_ok)
    assert qt_updater.should_check_for_updates()
    assert settings.get("updater_check_all") is True

    # Test 3 - Same as the previous test, but check that clicking on cancel stores the
    # opposite decision.
    settings.set("updater_check_all", None)

    def click_cancel() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.cancel_button.click()  # type: ignore

    QtCore.QTimer.singleShot(500, click_cancel)
    assert not qt_updater.should_check_for_updates()
    assert settings.get("updater_check_all") is False

    # Test 4 - Same as the previous test, but check that clicking on "X" does not store
    # any decision.
    settings.set("updater_check_all", None, autosave=True)

    def click_x() -> None:
        dialog = qt_updater.dangerzone.app.activeWindow()
        dialog.close()

    QtCore.QTimer.singleShot(500, click_x)
    assert not qt_updater.should_check_for_updates()
    assert settings.get("updater_check_all") is None
