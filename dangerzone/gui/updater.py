"""A module that contains the logic for checking for updates."""

import json
import logging
import platform
import sys
import time
import typing
from typing import Any, Optional

from packaging import version

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

import markdown
import requests

from ..util import get_version
from .logic import Alert, DangerzoneGui

log = logging.getLogger(__name__)


MSG_CONFIRM_UPDATE_CHECKS = """\
<p><b>Do you want to be notified about new Dangerzone releases?</b></p>

<p>If <i>"Yes"</i>, Dangerzone will check the
<a href="https://github.com/freedomofpress/dangerzone/releases">latest releases page</a>
in github.com on startup. If <i>"No"</i>, Dangerzone will make no network requests and
won't inform you about new releases.</p>

<p>If you prefer another way of getting notified about new releases, we suggest adding
to your RSS reader our
<a href="https://fosstodon.org/@dangerzone.rss">Mastodon feed</a>. For more information
about updates, check
<a href="https://github.com/freedomofpress/dangerzone/wiki/Updates">this webpage</a>.</p>
"""

UPDATE_CHECK_COOLDOWN_SECS = 60 * 60 * 12  # Check for updates at most every 12 hours.


class UpdateCheckPrompt(Alert):
    """The prompt that asks the users if they want to enable update checks."""

    x_pressed = False

    def closeEvent(self, event: QtCore.QEvent) -> None:
        """Detect when a user has pressed "X" in the title bar.

        This function is called when a user clicks on "X" in the title bar. We want to
        differentiate between the user clicking on "Cancel" and clicking on "X", since
        in the second case, we want to remind them again on the next run.

        See: https://stackoverflow.com/questions/70851063/pyqt-differentiate-between-close-function-and-title-bar-close-x
        """
        self.x_pressed = True
        event.accept()

    def create_buttons_layout(self) -> QtWidgets.QHBoxLayout:
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        assert self.cancel_button is not None
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.ok_button)
        return buttons_layout


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


class UpdaterThread(QtCore.QThread):
    """Check asynchronously for Dangerzone updates.

    The Updater class is mainly responsible for the following:

    1. Asking the user if they want to enable update checks or not.
    2. Determining when it's the right time to check for updates.
    3. Hitting the GitHub releases API and learning about updates.

    Since checking for updates is a task that may take some time, we perform it
    asynchronously, in a Qt thread. This thread then triggers a signal, and informs
    whoever has connected to it.
    """

    finished = QtCore.Signal(UpdateReport)

    GH_RELEASE_URL = (
        "https://api.github.com/repos/freedomofpress/dangerzone/releases/latest"
    )
    REQ_TIMEOUT = 15

    def __init__(self, dangerzone: DangerzoneGui):
        super().__init__()
        self.dangerzone = dangerzone

    ###########
    # Helpers for updater settings
    #
    # These helpers make it easy to retrieve specific updater-related settings, as well
    # as save the settings file, only when necessary.

    @property
    def check(self) -> Optional[bool]:
        return self.dangerzone.settings.get("updater_check")

    @check.setter
    def check(self, val: bool) -> None:
        self.dangerzone.settings.set("updater_check", val, autosave=True)

    def prompt_for_checks(self) -> Optional[bool]:
        """Ask the user if they want to be informed about Dangerzone updates."""
        log.debug("Prompting the user for update checks")
        # FIXME: Handle the case where a user clicks on "X", instead of explicitly
        # making a choice. We should probably ask them again on the next run.
        prompt = UpdateCheckPrompt(
            self.dangerzone,
            message=MSG_CONFIRM_UPDATE_CHECKS,
            ok_text="Yes",
            cancel_text="No",
        )
        check = prompt.launch()
        if not check and prompt.x_pressed:
            return None
        return bool(check)

    def should_check_for_updates(self) -> bool:
        """Determine if we can check for updates based on settings and user prefs.

        Note that this method only checks if the user has expressed an interest for
        learning about new updates, and not whether we should actually make an update
        check. Those two things are distinct, actually. For example:

        * A user may have expressed that they want to learn about new updates.
        * A previous update check may have found out that there's a new version out.
        * Thus we will always show to the user the cached info about the new version,
          and won't make a new update check.
        """
        log.debug("Checking platform type")
        # TODO: Disable updates for Homebrew installations.
        if platform.system() == "Linux" and not getattr(sys, "dangerzone_dev", False):
            log.debug("Running on Linux, disabling updates")
            self.check = False
            return False

        log.debug("Checking if first run of Dangerzone")
        if self.dangerzone.settings.get("updater_last_check") is None:
            log.debug("Dangerzone is running for the first time, updates are stalled")
            self.dangerzone.settings.set("updater_last_check", 0, autosave=True)
            return False

        log.debug("Checking if user has already expressed their preference")
        if self.check is None:
            log.debug("User has not been asked yet for update checks")
            self.check = self.prompt_for_checks()
            return bool(self.check)
        elif not self.check:
            log.debug("User has expressed that they don't want to check for updates")
            return False

        return True

    def can_update(self, cur_version: str, latest_version: str) -> bool:
        if version.parse(cur_version) == version.parse(latest_version):
            return False
        elif version.parse(cur_version) > version.parse(latest_version):
            # FIXME: This is a sanity check, but we should improve its wording.
            raise Exception("Received version is older than the latest version")
        else:
            return True

    def _get_now_timestamp(self) -> int:
        return int(time.time())

    def _should_postpone_update_check(self) -> bool:
        """Consult and update cooldown timer.

        If the previous check happened before the cooldown period expires, do not check
        again.
        """
        current_time = self._get_now_timestamp()
        last_check = self.dangerzone.settings.get("updater_last_check")
        if current_time < last_check + UPDATE_CHECK_COOLDOWN_SECS:
            log.debug(f"Cooling down update checks")
            return True
        else:
            return False

    def get_latest_info(self) -> UpdateReport:
        """Get the latest release info from GitHub.

        Also, render the changelog from Markdown format to HTML, so that we can show it
        to the users.
        """
        try:
            res = requests.get(self.GH_RELEASE_URL, timeout=self.REQ_TIMEOUT)
        except Exception as e:
            raise RuntimeError(
                f"Encountered an exception while checking {self.GH_RELEASE_URL}: {e}"
            )

        if res.status_code != 200:
            raise RuntimeError(
                f"Encountered an HTTP {res.status_code} error while checking"
                f" {self.GH_RELEASE_URL}"
            )

        try:
            info = res.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Received a non-JSON response from {self.GH_RELEASE_URL}")

        try:
            version = info["tag_name"].lstrip("v")
            changelog = markdown.markdown(info["body"])
        except KeyError as e:
            raise ValueError(
                f"Missing required fields in JSON response from {self.GH_RELEASE_URL}"
            )

        return UpdateReport(version=version, changelog=changelog)

    # XXX: This happens in parallel with other tasks. DO NOT alter global state!
    def _check_for_updates(self) -> UpdateReport:
        """Check for updates locally and remotely.

        Check for updates in two places:

        1. In our settings, in case we have cached the latest version/changelog from a
           previous run.
        2. In GitHub, by hitting the latest releases API.
        """
        log.debug(f"Checking for Dangerzone updates")
        latest_version = self.dangerzone.settings.get("updater_latest_version")
        if version.parse(get_version()) < version.parse(latest_version):
            log.debug(f"Determined that there is an update due to cached results")
            return UpdateReport(
                version=latest_version,
                changelog=self.dangerzone.settings.get("updater_latest_changelog"),
            )

        # If the previous check happened before the cooldown period expires, do not
        # check again. Else, bump the last check timestamp, before making the actual
        # check. This is to ensure that even failed update checks respect the cooldown
        # period.
        if self._should_postpone_update_check():
            return UpdateReport()
        else:
            self.dangerzone.settings.set(
                "updater_last_check", self._get_now_timestamp(), autosave=True
            )

        log.debug(f"Checking the latest GitHub release")
        report = self.get_latest_info()
        log.debug(f"Latest version in GitHub is {report.version}")
        if report.version and self.can_update(latest_version, report.version):
            log.debug(
                f"Determined that there is an update due to a new GitHub version:"
                f" {latest_version} < {report.version}"
            )
            return report

        log.debug(f"No need to update")
        return UpdateReport()

    ##################
    # Logic for running update checks asynchronously

    def check_for_updates(self) -> UpdateReport:
        """Check for updates and return a report with the findings:

        There are three scenarios when we check for updates, and each scenario returns a
        slightly different answer:

        1. No new updates: Return an empty update report.
        2. Updates are available: Return an update report with the latest version and
           changelog, in HTML format.
        3. Update check failed: Return an update report that holds just the error
           message.
        """
        try:
            res = self._check_for_updates()
        except Exception as e:
            log.exception("Encountered an error while checking for upgrades")
            res = UpdateReport(error=str(e))

        return res

    def run(self) -> None:
        self.finished.emit(self.check_for_updates())
