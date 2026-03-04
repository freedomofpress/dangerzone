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
from .logic import DangerzoneGui, Question

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
see <a href=https://github.com/freedomofpress/dangerzone/wiki/Updates>our
documentation ↗️</a>.</p>
"""
# FIXME: Add a link to the documentation.
OK_TEXT = "Yes, enable sandbox updates"
CANCEL_TEXT = "No, disable sandbox updates"

MSG_CONFIRM_DOWNLOAD_CONTAINER = """\
<p>
    <b>Enable sandbox download?</b>
</p>

<p>Dangerzone needs to download the sandbox from the internet to convert documents.</p>

<p>If you enable this option, Dangerzone will download the sandbox now and
periodically check for updates.</p>
<p>This is <b>required</b> for Dangerzone to work. If you prefer an offline install,
you can download the full version with an embedded container.</p>

<p>If you need to run Dangerzone in an air-gapped environment, see <a href="https://github.com/freedomofpress/dangerzone/blob/main/docs/developer/independent-container-updates.md#installing-image-updates-to-air-gapped-environments">our documentation</a>.</p>
"""
OK_TEXT_DOWNLOAD = "Yes, download sandbox"
CANCEL_TEXT_DOWNLOAD = "Quit Dangerzone"


class UpdateCheckPrompt(Question):
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


def prompt_for_checks(
    dangerzone: DangerzoneGui, download_required: bool = False
) -> Optional[bool]:
    """Prompt the user to enable update checks.

    Args:
        dangerzone: The DangerzoneGui instance.
        download_required: If True, no container is available and download is required.

    Returns:
        True if the user accepts enabling updates
        False if the user declines
        None if the user pressed X (dismissed without choosing)
    """
    if download_required:
        message = MSG_CONFIRM_DOWNLOAD_CONTAINER
        ok_text = OK_TEXT_DOWNLOAD
        cancel_text = CANCEL_TEXT_DOWNLOAD
        log.debug("Prompting the user for container download (no container available)")
    else:
        message = MSG_CONFIRM_UPDATE_CHECKS
        ok_text = OK_TEXT
        cancel_text = CANCEL_TEXT
        log.debug("Prompting the user for update checks")

    prompt = UpdateCheckPrompt(
        dangerzone,
        message=message,
        ok_text=ok_text,
        cancel_text=cancel_text,
    )
    check = prompt.launch()
    if check is not None and not prompt.x_pressed:
        return bool(check)
    else:
        return None
