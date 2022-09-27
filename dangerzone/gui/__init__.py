import logging
import os
import platform
import signal
import sys
import uuid
from typing import Dict, List, Optional

import click
import colorama
from PySide2 import QtCore, QtGui, QtWidgets

from .. import args, errors
from ..document import Document
from .logic import DangerzoneGui
from .main_window import MainWindow
from .systray import SysTray


# For some reason, Dangerzone segfaults if I inherit from QApplication directly, so instead
# this is a class whose job is to hold a QApplication object and customize it
class ApplicationWrapper(QtCore.QObject):
    document_selected = QtCore.Signal(str)
    new_window = QtCore.Signal()
    application_activated = QtCore.Signal()

    def __init__(self) -> None:
        super(ApplicationWrapper, self).__init__()
        self.app = QtWidgets.QApplication()
        self.app.setQuitOnLastWindowClosed(False)

        self.original_event = self.app.event

        def monkeypatch_event(arg__1: QtCore.QEvent) -> bool:
            event = arg__1  # oddly Qt calls internally event by "arg__1"
            # In macOS, handle the file open event
            if isinstance(event, QtGui.QFileOpenEvent):
                # Skip file open events in dev mode
                if not hasattr(sys, "dangerzone_dev"):
                    self.document_selected.emit(event.file())
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.app.event = monkeypatch_event  # type: ignore [assignment]


@click.command()
@click.argument(
    "filenames",
    required=False,
    nargs=-1,
    type=click.UNPROCESSED,
    callback=args.validate_input_filenames,
)
@errors.handle_document_errors
def gui_main(filenames: Optional[List[str]]) -> bool:
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
    app_wrapper = ApplicationWrapper()
    app = app_wrapper.app

    # Common objects
    dangerzone = DangerzoneGui(app)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create the system tray
    systray = SysTray(dangerzone, app, app_wrapper)

    closed_windows: Dict[str, MainWindow] = {}
    windows: Dict[str, MainWindow] = {}

    def delete_window(window_id: str) -> None:
        closed_windows[window_id] = windows[window_id]
        del windows[window_id]

    # Open a document in a window
    def new_window(filenames: Optional[List[str]] = []) -> None:
        window_id = uuid.uuid4().hex
        window = MainWindow(dangerzone, window_id)
        if filenames:
            window.content_widget.doc_selection_widget.document_selected.emit(filenames)
        window.delete_window.connect(delete_window)
        windows[window_id] = window

    new_window(filenames)

    # Open a new window, if all windows are closed
    def application_activated() -> None:
        if len(windows) == 0:
            new_window()

    # If we get a file open event, open it
    app_wrapper.document_selected.connect(new_window)
    app_wrapper.new_window.connect(new_window)

    # If the application is activated and all windows are closed, open a new one
    app_wrapper.application_activated.connect(application_activated)

    # Launch the GUI
    ret = app.exec_()

    sys.exit(ret)


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
