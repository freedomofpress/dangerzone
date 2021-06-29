import os
import sys
import signal
import platform
import click
import uuid
from PySide2 import QtCore, QtWidgets

from .common import GuiCommon
from .main_window import MainWindow
from .systray import SysTray
from .docker_installer import (
    is_docker_installed,
    is_docker_ready,
    DockerInstaller,
    AuthorizationFailed,
)
from ..global_common import GlobalCommon


# For some reason, Dangerzone segfaults if I inherit from QApplication directly, so instead
# this is a class whose job is to hold a QApplication object and customize it
class ApplicationWrapper(QtCore.QObject):
    document_selected = QtCore.Signal(str)
    application_activated = QtCore.Signal()

    def __init__(self):
        super(ApplicationWrapper, self).__init__()
        self.app = QtWidgets.QApplication()
        self.app.setQuitOnLastWindowClosed(False)

        self.original_event = self.app.event

        def monkeypatch_event(event):
            # In macOS, handle the file open event
            if event.type() == QtCore.QEvent.FileOpen:
                self.document_selected.emit(event.file())
                return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True

            return self.original_event(event)

        self.app.event = monkeypatch_event


@click.command()
@click.option("--custom-container")  # Use this container instead of flmcode/dangerzone
@click.argument("filename", required=False)
def gui_main(custom_container, filename):
    # Required for macOS Big Sur: https://stackoverflow.com/a/64878899
    if platform.system() == "Darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"

    # Create the Qt app
    app_wrapper = ApplicationWrapper()
    app = app_wrapper.app

    # Common objects
    global_common = GlobalCommon()
    gui_common = GuiCommon(app, global_common)

    global_common.display_banner()

    if custom_container:
        success, error_message = global_common.container_exists(custom_container)
        if not success:
            click.echo(error_message)
            return

        global_common.custom_container = custom_container

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # If we're using Linux and docker, see if we need to add the user to the docker group or if the user prefers typing their password
    if platform.system() == "Linux":
        if not gui_common.ensure_docker_group_preference():
            return
        try:
            if not gui_common.ensure_docker_service_is_started():
                click.echo("Failed to start docker service")
                return
        except AuthorizationFailed:
            click.echo("Authorization failed")
            return

    # See if we need to install Docker...
    if (platform.system() == "Darwin" or platform.system() == "Windows") and (
        not is_docker_installed() or not is_docker_ready(global_common)
    ):
        click.echo("Docker is either not installed or not running")
        docker_installer = DockerInstaller(gui_common)
        docker_installer.start()
        return

    closed_windows = {}
    windows = {}

    def delete_window(window_id):
        closed_windows[window_id] = windows[window_id]
        del windows[window_id]

    # Open a document in a window
    def select_document(filename=None):
        if (
            len(windows) == 1
            and windows[list(windows.keys())[0]].common.document_filename == None
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
            window.common.document_filename = filename
            window.doc_selection_widget.document_selected.emit()

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

    # If the application is activated and all windows are closed, open a new one
    app_wrapper.application_activated.connect(application_activated)

    # Create a system tray, which also handles the VM subprocess
    systray = SysTray(global_common, gui_common, app)

    sys.exit(app.exec_())
