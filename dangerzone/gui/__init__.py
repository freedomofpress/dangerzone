import functools
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
from ..util import get_resource_path
from .logic import DangerzoneGui
from .main_window import MainWindow


class Application(QtWidgets.QApplication):
    document_selected = QtCore.Signal(str)
    new_window = QtCore.Signal()
    application_activated = QtCore.Signal()

    def __init__(self) -> None:
        super(Application, self).__init__()
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
                    self.document_selected.emit(event.file())
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.event = monkeypatch_event  # type: ignore [assignment]


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
    app = Application()

    # Common objects
    dangerzone = DangerzoneGui(app)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

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
    app.document_selected.connect(new_window)
    app.new_window.connect(new_window)

    # If the application is activated and all windows are closed, open a new one
    app.application_activated.connect(application_activated)

    # Launch the GUI
    ret = app.exec_()

    sys.exit(ret)


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")


args.override_parser_and_check_suspicious_options(gui_main)
