import logging
import os
import platform
import signal
import sys
import uuid

import click
from PySide2 import QtCore, QtWidgets

from ..global_common import GlobalCommon
from .common import GuiCommon
from .main_window import MainWindow
from .systray import SysTray


# For some reason, Dangerzone segfaults if I inherit from QApplication directly, so instead
# this is a class whose job is to hold a QApplication object and customize it
class ApplicationWrapper(QtCore.QObject):
    document_selected = QtCore.Signal(str)
    new_window = QtCore.Signal()
    application_activated = QtCore.Signal()

    def __init__(self):
        super(ApplicationWrapper, self).__init__()
        self.app = QtWidgets.QApplication()
        self.app.setQuitOnLastWindowClosed(False)

        self.original_event = self.app.event

        def monkeypatch_event(event):
            # In macOS, handle the file open event
            if event.type() == QtCore.QEvent.FileOpen:
                # Skip file open events in dev mode
                if not hasattr(sys, "dangerzone_dev"):
                    self.document_selected.emit(event.file())
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.app.event = monkeypatch_event


@click.command()
@click.argument("filename", required=False)
def gui_main(filename):
    setup_logging()

    if platform.system() == "Darwin":
        # Required for macOS Big Sur: https://stackoverflow.com/a/64878899
        os.environ["QT_MAC_WANTS_LAYER"] = "1"

        # Make sure /usr/local/bin is in the path
        os.environ["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"

        # Strip ANSI colors from stdout output, to prevent terminal colors from breaking
        # the macOS GUI app
        from strip_ansi import strip_ansi

        class StdoutFilter:
            def __init__(self, stream):
                self.stream = stream

            def __getattr__(self, attr_name):
                return getattr(self.stream, attr_name)

            def write(self, data):
                self.stream.write(strip_ansi(data))

            def flush(self):
                self.stream.flush()

        sys.stdout = StdoutFilter(sys.stdout)
        sys.stderr = StdoutFilter(sys.stderr)

    # Create the Qt app
    app_wrapper = ApplicationWrapper()
    app = app_wrapper.app

    # Common objects
    global_common = GlobalCommon()
    gui_common = GuiCommon(app, global_common)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create the system tray
    systray = SysTray(global_common, gui_common, app, app_wrapper)

    closed_windows = {}
    windows = {}

    def delete_window(window_id):
        closed_windows[window_id] = windows[window_id]
        del windows[window_id]

    # Open a document in a window
    def select_document(filename=None):
        if (
            len(windows) == 1
            and windows[list(windows.keys())[0]].common.input_filename == None
        ):
            window = windows[list(windows.keys())[0]]
        else:
            window_id = uuid.uuid4().hex
            window = MainWindow(global_common, gui_common, window_id)
            window.delete_window.connect(delete_window)
            windows[window_id] = window

        if filename:
            # Validate filename
            filename = os.path.abspath(os.path.expanduser(filename))
            try:
                open(filename, "rb")
            except FileNotFoundError:
                click.echo("File not found")
                return False
            except PermissionError:
                click.echo("Permission denied")
                return False
            window.common.input_filename = filename
            window.content_widget.doc_selection_widget.document_selected.emit()

        return True

    # Open a new window if not filename is passed
    if filename is None:
        select_document()
    else:
        # If filename is passed as an argument, open it
        if not select_document(filename):
            return True

    # Open a new window, if all windows are closed
    def application_activated():
        if len(windows) == 0:
            select_document()

    # If we get a file open event, open it
    app_wrapper.document_selected.connect(select_document)
    app_wrapper.new_window.connect(select_document)

    # If the application is activated and all windows are closed, open a new one
    app_wrapper.application_activated.connect(application_activated)

    # Launch the GUI
    ret = app.exec_()

    sys.exit(ret)


def setup_logging() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
