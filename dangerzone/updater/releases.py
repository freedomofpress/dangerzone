import json
import platform
import sys
import time
from abc import ABC
from dataclasses import dataclass

# The "|" syntax for type unions was introduced with Python 3.10
# So we use Union instead as we still require Python 3.9
from typing import Optional, Tuple, Union

import markdown
import requests
from packaging import version

from .. import container_utils, util
from ..settings import Settings
from . import errors, log
from .signatures import (
    DEFAULT_PUBKEY_LOCATION,
    get_remote_digest_and_logindex,
)

# Check for updates at most every 12 hours.
UPDATE_CHECK_COOLDOWN_SECS = 60 * 60 * 12

GH_RELEASE_URL = (
    "https://api.github.com/repos/freedomofpress/dangerzone/releases/latest"
)
REQ_TIMEOUT = 15


@dataclass
class ReleaseReport:
    """
    A new Github Release, a new sandbox image (or both) have been detected
    """

    version: Optional[str] = None
    changelog: Optional[str] = None
    container_image_bump: bool = False

    @property
    def new_github_release(self) -> bool:
        return self.version is not None

    @property
    def is_empty(self) -> bool:
        return (
            self.version is None
            and self.changelog is None
            and not self.container_image_bump
        )


class EmptyReport:
    """Empty report, when there is nothing to report"""

    pass


@dataclass
class ErrorReport:
    """An error has been encountered when fetching updates"""

    error: str


def _get_now_timestamp() -> int:
    return int(time.time())


def _should_postpone_update_check(settings: Settings) -> bool:
    """Consult and update cooldown timer.

    If the previous check happened before the cooldown period expires, do not check
    again.
    """
    current_time = _get_now_timestamp()
    last_check = settings.get("updater_last_check")
    if current_time < last_check + UPDATE_CHECK_COOLDOWN_SECS:
        log.debug("Cooling down update checks")
        return True
    else:
        return False


def ensure_sane_update(cur_version: str, latest_version: str) -> bool:
    if version.parse(cur_version) == version.parse(latest_version):
        return False
    elif version.parse(cur_version) > version.parse(latest_version):
        raise Exception(
            "The version received from Github Releases is older than the latest known version"
        )
    else:
        return True


def fetch_github_release_info() -> Tuple[str, str]:
    """Get the latest release info from GitHub.

    Also, render the changelog from Markdown format to HTML, so that we can show it
    to the users.
    """
    log.debug("Checking the latest GitHub release")
    try:
        res = requests.get(GH_RELEASE_URL, timeout=REQ_TIMEOUT)
    except Exception as e:
        raise RuntimeError(
            f"Encountered an exception while checking {GH_RELEASE_URL}: {e}"
        )

    if res.status_code != 200:
        raise RuntimeError(
            f"Encountered an HTTP {res.status_code} error while checking"
            f" {GH_RELEASE_URL}"
        )

    try:
        info = res.json()
    except json.JSONDecodeError:
        raise ValueError(f"Received a non-JSON response from {GH_RELEASE_URL}")

    try:
        version = info["tag_name"].lstrip("v")
        changelog = markdown.markdown(info["body"])
    except KeyError:
        raise ValueError(
            f"Missing required fields in JSON response from {GH_RELEASE_URL}"
        )

    log.debug(f"Latest version in GitHub is {version}")
    return version, changelog


def should_check_for_updates(settings: Settings) -> bool:
    """Determine if we can check for release updates based on settings and user prefs.

    Note that this method only checks if the user has expressed an interest for
    learning about new updates, and not whether we should actually make an update
    check. Those two things are distinct, actually. For example:

    * A user may have expressed that they want to learn about new updates.
    * A previous update check may have found out that there's a new version out.
    * Thus we will always show to the user the cached info about the new version,
      and won't make a new update check.
    """
    check = settings.get("updater_check_all")

    # TODO: Disable updates for Homebrew installations.
    if platform.system() == "Linux" and not getattr(sys, "dangerzone_dev", False):
        log.debug("Running on Linux, disabling updates")
        if not check:  # if not overridden by user
            settings.set("updater_check_all", False, autosave=True)
            return False

    if settings.get("updater_last_check") is None:
        log.debug("Dangerzone is running for the first time, updates are stalled")
        settings.set("updater_last_check", 0, autosave=True)
        return False

    if check is None:
        log.debug("User has not been asked yet for update checks")
        raise errors.NeedUserInput()
    elif not check:
        log.debug("User has expressed that they don't want to check for updates")
        return False

    return True


def check_for_updates(
    settings: Settings,
) -> Union[ReleaseReport, EmptyReport, ErrorReport]:
    """
    Check for updates and return a report with the findings.

    Checks are spaced by a cooldown period, defined by the
    UPDATE_CHECK_COOLDOWN_SECS constant.
    """
    try:
        # If we already know from a previous run that there is a pending Github Release
        # return the report.
        latest_version = settings.get("updater_latest_version")
        new_gh_version = version.parse(util.get_version()) < version.parse(
            latest_version
        )

        if new_gh_version:
            return ReleaseReport(
                version=latest_version,
                changelog=settings.get("updater_latest_changelog"),
            )

        # If the previous check happened before the cooldown period expires, do not
        # check again. Else, bump the last check timestamp, before making the actual
        # check. This is to ensure that even failed update checks respect the cooldown
        # period.
        if _should_postpone_update_check(settings):
            return EmptyReport()
        else:
            settings.set("updater_last_check", _get_now_timestamp(), autosave=True)

        gh_version, gh_changelog = fetch_github_release_info()

        report = ReleaseReport()
        if gh_version and ensure_sane_update(latest_version, gh_version):
            log.debug(f"New GitHub release detected: {latest_version} < {gh_version}")
            report.version = gh_version
            report.changelog = gh_changelog

        container_name = container_utils.expected_image_name()
        previous_remote_log_index = settings.get("updater_remote_log_index")
        _, remote_log_index, _ = get_remote_digest_and_logindex(container_name)

        settings.set("updater_remote_log_index", remote_log_index, autosave=True)

        if previous_remote_log_index < remote_log_index:
            report.container_image_bump = True

        if report.is_empty:
            return EmptyReport()
        return report

    except Exception as e:
        log.exception("Encountered an error while checking for upgrades")
        return ErrorReport(error=str(e))
