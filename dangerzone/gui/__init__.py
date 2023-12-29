import enum
import functools
import logging
import os
import platform
import signal
import sys
import typing
import uuid
from typing import Dict, List, Optional

import click
import colorama

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

from .. import args, errors
from ..document import Document
from ..isolation_provider.container import Container
from ..isolation_provider.dummy import Dummy
from ..isolation_provider.qubes import Qubes, is_qubes_native_conversion
from ..util import get_resource_path, get_version
from .logic import DangerzoneGui
from .main_window import MainWindow
from .updater import UpdaterThread

log = logging.getLogger(__name__)


class OSColorMode(enum.Enum):
    """
    Operating system color mode, e.g. Light or Dark Mode on macOS 10.14+ or Windows 10+.

    The enum values are used as the names of Qt properties that will be selected by QSS
    property selectors to set color-mode-specific style rules.
    """

    LIGHT = "light"
    DARK = "dark"


class Application(QtWidgets.QApplication):
    document_selected = QtCore.Signal(list)
    application_activated = QtCore.Signal()

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super(Application, self).__init__(*args, **kwargs)
        self.setQuitOnLastWindowClosed(False)
        with open(get_resource_path("dangerzone.css"), "r") as f:
            style = f.read()
        self.setStyleSheet(style)
        self.original_event = self.event

        def monkeypatch_event(arg__1: QtCore.QEvent) -> bool:
            event = arg__1  # oddly Qt calls internally event by "arg__1"
            # In macOS, handle the file open event
            if isinstance(event, QtGui.QFileOpenEvent):
                # Skip file open events in dev mode
                if not hasattr(sys, "dangerzone_dev"):
                    self.document_selected.emit([event.file()])
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.event = monkeypatch_event  # type: ignore [method-assign]

        self.os_color_mode = self.infer_os_color_mode()
        log.debug(f"Inferred system color scheme as {self.os_color_mode}")

    def infer_os_color_mode(self) -> OSColorMode:
        """
        Qt 6.5+ explicitly provides the OS color scheme via QStyleHints.colorScheme(),
        but we still need to support PySide2/Qt 5, so instead we infer the OS color
        scheme from the default palette.
        """
        text_color, window_color = (
            self.palette().color(role)
            for role in (QtGui.QPalette.WindowText, QtGui.QPalette.Window)
        )
        if text_color.lightness() > window_color.lightness():
            return OSColorMode.DARK
        return OSColorMode.LIGHT


@click.command()
@click.option(
    "--unsafe-dummy-conversion", "dummy_conversion", flag_value=True, hidden=True
)
@click.option(
    "--enable-timeouts / --disable-timeouts",
    default=True,
    show_default=True,
    help="Enable/Disable timeouts during document conversion",
)
@click.argument(
    "filenames",
    required=False,
    nargs=-1,
    type=click.UNPROCESSED,
    callback=args.validate_input_filenames,
)
@click.version_option(version=get_version(), message="%(version)s")
@errors.handle_document_errors
def gui_main(
    dummy_conversion: bool, filenames: Optional[List[str]], enable_timeouts: bool
) -> bool:
    setup_logging()

    if platform.system() == "Darwin":
        # Required for macOS Big Sur: https://stackoverflow.com/a/64878899
        os.environ["QT_MAC_WANTS_LAYER"] = "1"

        # Make sure /usr/local/bin is in the path
        os.environ["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"

        # Don't show ANSI colors from stdout output, to prevent terminal
        # colors from breaking the macOS GUI app
        colorama.deinit()

    # Create the Qt app
    app = Application()

    # Common objects
    if getattr(sys, "dangerzone_dev", False) and dummy_conversion:
        dummy = Dummy()
        dangerzone = DangerzoneGui(app, isolation_provider=dummy)
    elif is_qubes_native_conversion():
        qubes = Qubes()
        dangerzone = DangerzoneGui(app, isolation_provider=qubes)
    else:
        container = Container(enable_timeouts=enable_timeouts)
        dangerzone = DangerzoneGui(app, isolation_provider=container)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    def open_files(filenames: List[str] = []) -> None:
        documents = [Document(filename) for filename in filenames]
        window.content_widget.doc_selection_widget.documents_selected.emit(documents)

    window = MainWindow(dangerzone)

    # Check for updates
    log.debug("Setting up Dangerzone updater")
    updater = UpdaterThread(dangerzone)
    window.register_update_handler(updater.finished)

    log.debug("Consulting updater settings before checking for updates")
    if updater.should_check_for_updates():
        log.debug("Checking for updates")
        updater.start()
    else:
        log.debug("Will not check for updates, based on updater settings")

    # Ensure the status of the toggle updates checkbox is updated, after the user is
    # prompted to enable updates.
    window.toggle_updates_action.setChecked(bool(updater.check))

    if filenames:
        open_files(filenames)

    # MacOS: Open a new window, if all windows are closed
    def application_activated() -> None:
        window.show()

    # If we get a file open event, open it
    app.document_selected.connect(open_files)

    # If the application is activated and all windows are closed, open a new one
    app.application_activated.connect(application_activated)

    # Launch the GUI
    ret = app.exec_()

    sys.exit(ret)


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")


args.override_parser_and_check_suspicious_options(gui_main)
