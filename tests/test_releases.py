"""Tests for the updater releases module."""

import platform
import sys
from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest
from pytest_mock import MockerFixture

from dangerzone.settings import Settings
from dangerzone.updater.releases import (
    UPDATE_CHECK_COOLDOWN_SECS,
    EmptyReport,
    ErrorReport,
    ReleaseReport,
    _get_now_timestamp,
    check_for_updates,
)


@pytest.fixture
def mock_settings(mocker: MockerFixture, tmp_path: Any) -> Settings:
    """Create a mock settings object with a temporary config directory."""
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    Settings._singleton = None
    settings = Settings()
    settings.set("updater_check_all", True)
    settings.set("updater_last_check", 0)
    settings.set("updater_latest_version", "0.1.0")
    settings.set("updater_latest_changelog", "")
    settings.set("updater_remote_log_index", 0)
    settings.save()
    return settings


def test_new_dz_versions_are_skipped_on_linux(
    mocker: MockerFixture, mock_settings: Settings
) -> None:
    """Test that GitHub release checks are skipped on Linux (users get updates from package manager)."""
    # Mock platform to be Linux
    mocker.patch("dangerzone.updater.releases.platform.system", return_value="Linux")
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Mock the current version
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")

    # Mock GitHub release fetch to return a newer version
    mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info",
        return_value=("0.2.0", "<p>New release</p>"),
    )

    # Mock container image check to return no updates
    mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=("digest123", 0, []),
    )
    mocker.patch(
        "dangerzone.updater.releases.container_utils.expected_image_name",
        return_value="dangerzone/container",
    )

    # Set last check to old timestamp to avoid cooldown
    mock_settings.set("updater_last_check", 0, autosave=True)

    # Check for updates
    report = check_for_updates(mock_settings)

    # On Linux, GitHub releases should not be checked
    # fetch_github_release_info should not have been called
    mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info"
    ).assert_not_called()

    # Report should be empty since no container update was detected
    assert isinstance(report, EmptyReport)


@pytest.mark.parametrize(
    "platform_system,gh_release_check",
    [
        ("Linux", False),  # Linux skips GitHub checks
        ("Darwin", True),  # macOS checks GitHub
        ("Windows", True),  # Windows checks GitHub
    ],
)
def test_new_sandbox_is_checked_on_all_platforms(
    mocker: MockerFixture,
    mock_settings: Settings,
    platform_system: str,
    gh_release_check: bool,
) -> None:
    """Test that container image updates are checked on all platforms."""
    # Mock platform
    mocker.patch(
        "dangerzone.updater.releases.platform.system", return_value=platform_system
    )
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Mock the current version
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")

    # Mock GitHub release fetch (should only be called on non-Linux)
    mock_gh_fetch = mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info",
        return_value=("0.1.0", "<p>Same version</p>"),  # No new version
    )

    # Mock container image check to return a new log index (update available)
    mock_container_check = mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=("digest123", 100, []),  # New log index: 100
    )
    mocker.patch(
        "dangerzone.updater.releases.container_utils.expected_image_name",
        return_value="dangerzone/container",
    )

    # Set old remote log index to detect update
    mock_settings.set("updater_remote_log_index", 50, autosave=True)
    mock_settings.set("updater_last_check", 0, autosave=True)  # Avoid cooldown

    # Check for updates
    report = check_for_updates(mock_settings)

    # Container check should be called on ALL platforms
    mock_container_check.assert_called_once()

    # GitHub check should only be called on non-Linux platforms
    if gh_release_check:
        mock_gh_fetch.assert_called_once()
    else:
        mock_gh_fetch.assert_not_called()

    # Report should indicate container image bump
    assert isinstance(report, ReleaseReport)
    assert report.container_image_bump is True

    # Updated remote log index should be saved
    assert mock_settings.get("updater_remote_log_index") == 100


def test_updates_are_postponed_if_needed(
    mocker: MockerFixture, mock_settings: Settings
) -> None:
    """Test that update checks respect the cooldown period."""
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Mock current version (needed for cached version check)
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")
    current_time = _get_now_timestamp()
    mock_settings.set(
        "updater_last_check",
        current_time - (UPDATE_CHECK_COOLDOWN_SECS // 2),  # Half cooldown period ago
        autosave=True,
    )

    # Mock GitHub and container checks (they shouldn't be called)
    mock_gh_fetch = mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info",
        return_value=("0.2.0", "<p>New release</p>"),
    )
    mock_container_check = mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=("digest123", 100, []),
    )

    # Check for updates
    report = check_for_updates(mock_settings)

    # Should return empty report due to cooldown
    assert isinstance(report, EmptyReport)

    # Neither GitHub nor container checks should have been called
    mock_gh_fetch.assert_not_called()
    mock_container_check.assert_not_called()


def test_updates_proceed_after_cooldown_expires(
    mocker: MockerFixture, mock_settings: Settings
) -> None:
    """Test that update checks proceed after the cooldown period expires."""
    mocker.patch("dangerzone.updater.releases.platform.system", return_value="Darwin")
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Get current timestamp
    current_time = _get_now_timestamp()

    # Set last check to be beyond the cooldown period
    mock_settings.set(
        "updater_last_check",
        current_time - UPDATE_CHECK_COOLDOWN_SECS - 100,  # Past cooldown
        autosave=True,
    )

    # Mock current version and GitHub check
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")
    mock_gh_fetch = mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info",
        return_value=("0.2.0", "<p>New release</p>"),
    )

    # Mock container check
    mock_container_check = mocker.patch(
        "dangerzone.updater.releases.get_remote_digest_and_logindex",
        return_value=("digest123", 100, []),
    )
    mocker.patch(
        "dangerzone.updater.releases.container_utils.expected_image_name",
        return_value="dangerzone/container",
    )

    # Set latest version to old value
    mock_settings.set("updater_latest_version", "0.1.0", autosave=True)
    mock_settings.set("updater_remote_log_index", 0, autosave=True)

    # Check for updates
    report = check_for_updates(mock_settings)

    # Both checks should have been called
    mock_gh_fetch.assert_called_once()
    mock_container_check.assert_called_once()

    # Report should have both updates
    assert isinstance(report, ReleaseReport)
    assert report.version == "0.2.0"
    assert report.changelog == "<p>New release</p>"
    assert report.container_image_bump is True


def test_cached_github_release_is_returned_on_subsequent_checks(
    mocker: MockerFixture, mock_settings: Settings
) -> None:
    """Test that a cached GitHub release is returned without making a new network request."""
    # Mock platform
    mocker.patch("dangerzone.updater.releases.platform.system", return_value="Darwin")
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Mock current version to be older than cached version
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")

    # Set cached version to newer version
    mock_settings.set("updater_latest_version", "0.2.0", autosave=True)
    mock_settings.set(
        "updater_latest_changelog", "<p>Cached release</p>", autosave=True
    )

    # Mock GitHub fetch (should not be called)
    mock_gh_fetch = mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info"
    )

    # Check for updates
    report = check_for_updates(mock_settings)

    # Should return cached release without making a network request
    assert isinstance(report, ReleaseReport)
    assert report.version == "0.2.0"
    assert report.changelog == "<p>Cached release</p>"

    # GitHub fetch should not have been called
    mock_gh_fetch.assert_not_called()


def test_error_report_is_returned_on_exception(
    mocker: MockerFixture, mock_settings: Settings
) -> None:
    """Test that an ErrorReport is returned when an exception occurs during update check."""
    # Mock platform
    mocker.patch("dangerzone.updater.releases.platform.system", return_value="Darwin")
    mocker.patch.object(sys, "dangerzone_dev", False, create=True)

    # Mock current version
    mocker.patch("dangerzone.util.get_version", return_value="0.1.0")

    # Set last check to avoid cooldown
    mock_settings.set("updater_last_check", 0, autosave=True)
    mock_settings.set("updater_latest_version", "0.1.0", autosave=True)

    # Mock GitHub fetch to raise an exception
    mocker.patch(
        "dangerzone.updater.releases.fetch_github_release_info",
        side_effect=RuntimeError("Network error"),
    )

    # Check for updates
    report = check_for_updates(mock_settings)

    # Should return ErrorReport
    assert isinstance(report, ErrorReport)
    assert "Network error" in report.error
