import json
import platform
import sys
import time
import typing
from pathlib import Path
from typing import Any, Dict, Union

import pytest
from pytest import MonkeyPatch, fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

from dangerzone import settings
from dangerzone.gui.logic import Alert, DangerzoneGui
from dangerzone.gui.updater import CANCEL_TEXT, OK_TEXT, prompt_for_checks
from dangerzone.updater import releases
from dangerzone.updater.releases import (
    EmptyReport,
    ErrorReport,
    ReleaseReport,
)
from dangerzone.util import get_version

from ..test_settings import default_settings_0_4_1, save_settings


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
    assert isinstance(report1, (ReleaseReport, EmptyReport, ErrorReport))
    assert isinstance(report2, (ReleaseReport, EmptyReport, ErrorReport))
    assert type(report1) == type(report2)
    # Python dataclasses give us the __eq__ comparison for free
    assert report1.__eq__(report2)


def test_default_updater_settings(isolated_settings: settings.Settings) -> None:
    """Check that new 0.4.2 installations have the expected updater settings.

    This test is mostly a sanity check.
    """
    assert isolated_settings.get_updater_settings() == default_updater_settings()


def test_pre_0_4_2_settings(isolated_settings: settings.Settings) -> None:
    """Check settings of installations prior to 0.4.2.

    Check that installations that have been upgraded from a version < 0.4.2 to >= 0.4.2
    will automatically get the default updater settings, even though they never existed
    in their settings.json file.
    """
    tmp_path = isolated_settings.settings_filename.parent
    save_settings(tmp_path, default_settings_0_4_1())
    assert isolated_settings.get_updater_settings() == default_updater_settings()


def test_post_0_4_2_settings(
    isolated_settings: settings.Settings,
    monkeypatch: MonkeyPatch,
) -> None:
    """Check settings of installations post-0.4.2.

    Installations from 0.4.2 onwards will have a "updater_latest_version" field in their
    settings. When these installations get upgraded to a newer version, we must make
    sure that this field becomes equal to the new version, so that the user is not
    erroneously prompted to a version they already have.
    """
    # Store the settings of Dangerzone 0.4.2 to the filesystem.
    tmp_path = isolated_settings.settings_filename.parent
    old_settings = settings.Settings.generate_default_settings()
    old_settings["updater_latest_version"] = "0.4.2"
    # isolated_settings.set("updater_last_check", 0)
    save_settings(tmp_path, old_settings)

    # Mimic an upgrade to version 0.4.3, by making Dangerzone report that the current
    # version is 0.4.3.
    expected_settings = default_updater_settings()
    expected_settings["updater_latest_version"] = "0.4.3"
    monkeypatch.setattr(settings, "get_version", lambda: "0.4.3")

    # Ensure that the Settings class will correct the latest version field to 0.4.3.
    isolated_settings.load()
    assert isolated_settings.get_updater_settings() == expected_settings

    # Simulate an updater check that found a newer Dangerzone version (e.g., 0.4.4).
    expected_settings["updater_latest_version"] = "0.4.4"
    isolated_settings.set(
        "updater_latest_version", expected_settings["updater_latest_version"]
    )
    isolated_settings.save()

    # Ensure that the Settings class will leave the "updater_latest_version" field
    # intact the next time we reload the settings.
    isolated_settings.load()
    assert isolated_settings.get_updater_settings() == expected_settings


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only test")
def test_linux_no_check(
    isolated_settings: settings.Settings, monkeypatch: MonkeyPatch
) -> None:
    """Ensure that Dangerzone on Linux does not make any update check."""
    expected_settings = default_updater_settings()
    expected_settings["updater_check_all"] = False
    expected_settings["updater_last_check"] = None

    # XXX: Simulate Dangerzone installed via package manager.
    monkeypatch.delattr(sys, "dangerzone_dev")

    assert releases.should_check_for_updates(isolated_settings) is False
    assert isolated_settings.get_updater_settings() == expected_settings


def test_update_checks(
    isolated_settings: settings.Settings,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test version update checks."""
    settings = isolated_settings
    # This dictionary will simulate GitHub's response.
    mock_upstream_info = {"tag_name": f"v{get_version()}", "body": "changelog"}

    # Make requests.get().json() return the above dictionary.
    requests_mock = mocker.patch("dangerzone.updater.releases.requests.get")
    requests_mock().status_code = 200
    requests_mock().json.return_value = mock_upstream_info

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
    requests_mock.side_effect = Exception("failed")
    report = releases.check_for_updates(settings)
    error_msg = (
        f"Encountered an exception while checking {releases.GH_RELEASE_URL}: failed"
    )
    assert_report_equal(report, ErrorReport(error=error_msg))

    # Test 4 - Check that cached version/changelog info do not trigger an update check.
    settings.set("updater_latest_version", "99.9.9")
    settings.set("updater_latest_changelog", "<p>changelog</p>")

    report = releases.check_for_updates(settings)
    assert_report_equal(
        report, ReleaseReport(version="99.9.9", changelog="<p>changelog</p>")
    )


def test_update_checks_cooldown(
    isolated_settings: settings.Settings,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Make sure Dangerzone only checks for updates every X hours"""
    settings = isolated_settings

    settings.set("updater_check_all", True)
    settings.set("updater_last_check", 0)

    # Mock some functions before the tests start
    cooldown_spy = mocker.spy(releases, "_should_postpone_update_check")
    timestamp_mock = mocker.patch.object(releases, "_get_now_timestamp")
    requests_mock = mocker.patch("dangerzone.updater.releases.requests.get")

    # Mock the response of the container updater check
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 0, None],
    )

    # # Make requests.get().json() return the version info that we want.
    mock_upstream_info = {"tag_name": "99.9.9", "body": "changelog"}
    requests_mock().status_code = 200
    requests_mock().json.return_value = mock_upstream_info

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
    requests_mock.side_effect = Exception("failed")
    settings.set("updater_latest_version", get_version())
    settings.set("updater_latest_changelog", None)

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is True
    assert settings.get("updater_last_check") == curtime - 1  # type: ignore [unreachable]
    assert_report_equal(report, EmptyReport())

    # Test 3: Advance the current time by <cooldown period> seconds. Ensure that
    # Dangerzone checks for updates again, and the last check timestamp gets bumped.
    curtime += releases.UPDATE_CHECK_COOLDOWN_SECS
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

    curtime += releases.UPDATE_CHECK_COOLDOWN_SECS
    timestamp_mock.return_value = curtime
    requests_mock.side_effect = Exception("failed")

    report = releases.check_for_updates(settings)
    assert cooldown_spy.spy_return is False
    assert settings.get("updater_last_check") == curtime
    error_msg = (
        f"Encountered an exception while checking {releases.GH_RELEASE_URL}: failed"
    )
    assert_report_equal(report, ErrorReport(error=error_msg))


def test_update_errors(
    isolated_settings: settings.Settings,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    """Test update check errors."""
    settings = isolated_settings
    # Always assume that we can perform multiple update checks in a row.
    monkeypatch.setattr(releases, "_should_postpone_update_check", lambda _: False)
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=[None, 0, None],
    )

    # Mock requests.get().
    requests_mock = mocker.patch("dangerzone.updater.releases.requests.get")

    # Test 1 - Check that request exceptions are being detected as errors.
    requests_mock.side_effect = Exception("bad url")
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "bad url" in report.error
    assert "Encountered an exception" in report.error

    # Test 2 - Check that non HTTP 200 responses are detected as errors.
    class MockResponse500:
        status_code = 500

    requests_mock.return_value = MockResponse500()
    requests_mock.side_effect = None
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Encountered an HTTP 500 error" in report.error

    # Test 3 - Check that non JSON responses are detected as errors.
    class MockResponseBadJSON:
        status_code = 200

        def json(self) -> dict:
            return json.loads("bad json")

    requests_mock.return_value = MockResponseBadJSON()
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Received a non-JSON response" in report.error

    # Test 4 - Check that missing fields in JSON are detected as errors.
    class MockResponseEmpty:
        status_code = 200

        def json(self) -> dict:
            return {}

    requests_mock.return_value = MockResponseEmpty()
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Missing required fields in JSON" in report.error

    # Test 5 - Check invalid versions are reported
    class MockResponseBadVersion:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "vbad_version", "body": "changelog"}

    requests_mock.return_value = MockResponseBadVersion()
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None
    assert "Invalid version" in report.error

    # Test 6 - Check invalid markdown is reported
    class MockResponseBadMarkdown:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": ["bad", "markdown"]}

    requests_mock.return_value = MockResponseBadMarkdown()
    report = releases.check_for_updates(settings)
    assert type(report) == ErrorReport
    assert report.error is not None

    # Test 7 - Check that a valid response passes.
    class MockResponseValid:
        status_code = 200

        def json(self) -> dict:
            return {"tag_name": "v99.9.9", "body": "changelog"}

    requests_mock.return_value = MockResponseValid()
    report = releases.check_for_updates(settings)
    assert_report_equal(report, ReleaseReport("99.9.9", "<p>changelog</p>"))


def test_update_check_prompt(
    dangerzone_gui: DangerzoneGui,
) -> None:
    """Test that the prompt to enable update checks works properly."""

    # Force Dangerzone to check immediately for updates
    # Test 1 - The user is prompted to choose if they want to enable update checks, and
    # they agree.
    def check_button_labels() -> None:
        dialog = QtWidgets.QApplication.activeWindow()
        assert dialog.ok_button.text() == OK_TEXT  # type: ignore [attr-defined]
        assert dialog.cancel_button.text() == CANCEL_TEXT  # type: ignore [attr-defined]
        dialog.ok_button.click()  # type: ignore [attr-defined]

    QtCore.QTimer.singleShot(500, check_button_labels)
    assert prompt_for_checks(dangerzone_gui)

    # Test 2 - Same as the previous test, but the user disagrees.
    def click_cancel() -> None:
        dialog = QtWidgets.QApplication.activeWindow()
        dialog.cancel_button.click()  # type: ignore

    QtCore.QTimer.singleShot(500, click_cancel)
    assert not prompt_for_checks(dangerzone_gui)

    # Test 3 - Same as the previous test, but check that clicking on "X" does not store
    # any decision.
    def click_x() -> None:
        dialog = QtWidgets.QApplication.activeWindow()
        dialog.close()

    QtCore.QTimer.singleShot(500, click_x)
    assert prompt_for_checks(dangerzone_gui) is None
