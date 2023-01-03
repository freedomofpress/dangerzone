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
from ..isolation_provider.container import Container
from ..isolation_provider.dummy import Dummy
from ..util import get_resource_path, get_version
from .logic import DangerzoneGui
from .main_window import MainWindow


class Application(QtWidgets.QApplication):
    document_selected = QtCore.Signal(list)
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
                    self.document_selected.emit([event.file()])
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.event = monkeypatch_event  # type: ignore [assignment]


@click.command()
@click.option(
    "--unsafe-dummy-conversion", "dummy_conversion", flag_value=True, hidden=True
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
def gui_main(dummy_conversion: bool, filenames: Optional[List[str]]) -> bool:
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
    else:
        container = Container()
        dangerzone = DangerzoneGui(app, isolation_provider=container)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    def open_files(filenames: List[str] = []) -> None:
        documents = [Document(filename) for filename in filenames]
        window.content_widget.doc_selection_widget.documents_selected.emit(documents)

    window = MainWindow(dangerzone)
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
