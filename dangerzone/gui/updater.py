import logging
import typing
from typing import Optional

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

from ..updater import errors, releases
from .logic import Alert, DangerzoneGui

log = logging.getLogger(__name__)

MSG_CONFIRM_UPDATE_CHECKS = """\
<p>
    <b>Do you want Dangerzone to automatically check for updates and apply them?</b>
</p>

<p>If you accept, Dangerzone will check for updates of the sandbox and apply them
automatically. This will ensure that you always have the latest version of the sandbox,
which is critical for the software to operate securely.</p>

<p>Sandbox updates may include security patches and bug fixes, but won't include new features.</p>

<p>Additionally, Dangerzone will check the
<a href="https://github.com/freedomofpress/dangerzone/releases">latest releases page</a>
in github.com, and inform you about new releases.

Otherwise it will make no network requests and won't inform you about new releases.</p>

<p>If you prefer another way of getting notified about new releases, we suggest adding
to your RSS reader our
<a href="https://dangerzone.rocks/feed.xml">Dangerzone News feed</a>.</p>
"""


class UpdateCheckPrompt(Alert):
    """The prompt that asks the users if they want to enable update checks."""

    x_pressed = False

    def closeEvent(self, event: QtCore.QEvent) -> None:
        """Detect when a user has pressed "X" in the title bar (to close the dialog).

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
        self.ok_button.setDefault(True)
        return buttons_layout


class UpdaterThread(QtCore.QThread):
    """Check asynchronously for Dangerzone updates.

    The Updater class is mainly responsible for
    asking the user if they want to enable update checks or not.

    Since checking for updates is a task that may take some time, we perform it
    asynchronously, in a Qt thread.

    When finished, this thread triggers a signal with the results.
    """

    finished = QtCore.Signal(releases.UpdateReport)

    def __init__(self, dangerzone: DangerzoneGui):
        super().__init__()
        self.dangerzone = dangerzone

    def prompt_for_checks(self) -> Optional[bool]:
        """Ask the user if they want to be informed about Dangerzone updates."""
        log.debug("Prompting the user for update checks")
        prompt = UpdateCheckPrompt(
            self.dangerzone,
            message=MSG_CONFIRM_UPDATE_CHECKS,
            ok_text="Enable sandbox updates",
            cancel_text="Do not make any requests",
        )
        check = prompt.launch()
        if not check and prompt.x_pressed:
            return None
        return bool(check)

    def should_check_for_updates(self) -> bool:
        try:
            should_check: Optional[bool] = releases.should_check_for_releases(
                self.dangerzone.settings
            )
        except errors.NeedUserInput:
            should_check = self.prompt_for_checks()
            if should_check is not None:
                self.dangerzone.settings.set(
                    "updater_check_all", should_check, autosave=True
                )
        return bool(should_check)

    def run(self) -> None:
        has_updates = releases.check_for_updates(self.dangerzone.settings)
        self.finished.emit(has_updates)
