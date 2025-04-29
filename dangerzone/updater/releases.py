import json
import platform
import sys
import time
from typing import Optional

import markdown
import requests
from packaging import version

from .. import util
from ..settings import Settings
from . import errors, log

# Check for updates at most every 12 hours.
UPDATE_CHECK_COOLDOWN_SECS = 60 * 60 * 12

GH_RELEASE_URL = (
    "https://api.github.com/repos/freedomofpress/dangerzone/releases/latest"
)
REQ_TIMEOUT = 15


class UpdateReport:
    """A report for an update check."""

    def __init__(
        self,
        version: Optional[str] = None,
        changelog: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.version = version
        self.changelog = changelog
        self.error = error

    def empty(self) -> bool:
        return self.version is None and self.changelog is None and self.error is None


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
        # FIXME: This is a sanity check, but we should improve its wording.
        raise Exception("Received version is older than the latest version")
    else:
        return True


def fetch_release_info() -> UpdateReport:
    """Get the latest release info from GitHub.

    Also, render the changelog from Markdown format to HTML, so that we can show it
    to the users.
    """
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

    return UpdateReport(version=version, changelog=changelog)


def should_check_for_releases(settings: Settings) -> bool:
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

    log.debug("Checking platform type")
    # TODO: Disable updates for Homebrew installations.
    if platform.system() == "Linux" and not getattr(sys, "dangerzone_dev", False):
        log.debug("Running on Linux, disabling updates")
        if not check:  # if not overidden by user
            settings.set("updater_check_all", False, autosave=True)
            return False

    log.debug("Checking if first run of Dangerzone")
    if settings.get("updater_last_check") is None:
        log.debug("Dangerzone is running for the first time, updates are stalled")
        settings.set("updater_last_check", 0, autosave=True)
        return False

    log.debug("Checking if user has already expressed their preference")
    if check is None:
        log.debug("User has not been asked yet for update checks")
        raise errors.NeedUserInput()
    elif not check:
        log.debug("User has expressed that they don't want to check for updates")
        return False

    return True


def check_for_updates(settings: Settings) -> UpdateReport:
    """Check for updates locally and remotely.

    Check for updates (locally and remotely) and return a report with the findings:

    There are three scenarios when we check for updates, and each scenario returns a
    slightly different answer:

    1. No new updates: Return an empty update report.
    2. Updates are available: Return an update report with the latest version and
        changelog, in HTML format.
    3. Update check failed: Return an update report that holds just the error
        message.
    """
    try:
        log.debug("Checking for Dangerzone updates")
        latest_version = settings.get("updater_latest_version")
        if version.parse(util.get_version()) < version.parse(latest_version):
            log.debug("Determined that there is an update due to cached results")
            return UpdateReport(
                version=latest_version,
                changelog=settings.get("updater_latest_changelog"),
            )

        # If the previous check happened before the cooldown period expires, do not
        # check again. Else, bump the last check timestamp, before making the actual
        # check. This is to ensure that even failed update checks respect the cooldown
        # period.
        if _should_postpone_update_check(settings):
            return UpdateReport()
        else:
            settings.set("updater_last_check", _get_now_timestamp(), autosave=True)

        log.debug("Checking the latest GitHub release")
        report = fetch_release_info()
        log.debug(f"Latest version in GitHub is {report.version}")
        if report.version and ensure_sane_update(latest_version, report.version):
            log.debug(
                f"Determined that there is an update due to a new GitHub version:"
                f" {latest_version} < {report.version}"
            )
            return report

        log.debug("No need to update")
        return UpdateReport()
    except Exception as e:
        log.exception("Encountered an error while checking for upgrades")
        return UpdateReport(error=str(e))
