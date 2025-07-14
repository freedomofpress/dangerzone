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
    <b>Enable automatic sandbox updates?</b>
</p>

<p>If enabled, Dangerzone will periodically fetch and install updates for the
internal sandbox that it uses to convert documents. It will also notify you of
new Dangerzone releases.</p>

<p>This is recommended in most settings. For alternative methods to keep
Dangerzone up-to-date and secure (e.g., in a networkless environment),
see our documentation.</p>
"""
# FIXME: Add a link to the documentation.
OK_TEXT = "Yes, enable sandbox updates"
CANCEL_TEXT = "No, disable sandbox updates"


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


def prompt_for_checks(dangerzone: DangerzoneGui):
    """Check for Dangerzone updates.

    This function is responsible for asking the user if they want to enable
    update checks or not, and then performing the update check.
    """

    log.debug("Prompting the user for update checks")
    prompt = UpdateCheckPrompt(
        dangerzone,
        message=MSG_CONFIRM_UPDATE_CHECKS,
        ok_text=OK_TEXT,
        cancel_text=CANCEL_TEXT,
    )
    check = prompt.launch()
    if check is not None and not prompt.x_pressed:
        return bool(check)
    else:
        return None
