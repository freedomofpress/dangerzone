from PyQt5 import QtCore, QtWidgets
import os
import sys
import signal
import platform
import click
import time

from .global_common import GlobalCommon
from .main_window import MainWindow
from .docker_installer import (
    is_docker_installed,
    is_docker_ready,
    launch_docker_windows,
    DockerInstaller,
)

dangerzone_version = "0.0.3"


class Application(QtWidgets.QApplication):
    document_selected = QtCore.pyqtSignal(str)

    def __init__(self):
        QtWidgets.QApplication.__init__(self, sys.argv)

    def event(self, event):
        # In macOS, handle the file open event
        if event.type() == QtCore.QEvent.FileOpen:
            self.document_selected.emit(event.file())
            return True

        return QtWidgets.QApplication.event(self, event)


@click.command()
@click.argument("filename", required=False)
def main(filename):
    print(f"dangerzone {dangerzone_version}")

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create the Qt app
    app = Application()
    app.setQuitOnLastWindowClosed(False)

    # GlobalCommon object
    global_common = GlobalCommon(app)

    # If we're using Linux and docker, see if we need to add the user to the docker group
    if (
        platform.system() == "Linux"
        and global_common.container_runtime == "/usr/bin/docker"
    ):
        if not global_common.ensure_user_is_in_docker_group():
            print("Failed to add user to docker group")
            return

    # See if we need to install Docker...
    if (platform.system() == "Darwin" or platform.system() == "Windows") and (
        not is_docker_installed(global_common) or not is_docker_ready(global_common)
    ):
        print("Docker is either not installed or not running")
        docker_installer = DockerInstaller(global_common)
        docker_installer.start()
        return

    windows = []

    # Open a document in a window
    def select_document(filename=None):
        if len(windows) == 1 and windows[0].common.document_filename == None:
            window = windows[0]
        else:
            window = MainWindow(global_common)
            windows.append(window)

        if filename:
            # Validate filename
            filename = os.path.abspath(os.path.expanduser(filename))
            try:
                open(filename, "rb")
            except FileNotFoundError:
                print("File not found")
                return False
            except PermissionError:
                print("Permission denied")
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

    # If we get a file open event, open it
    app.document_selected.connect(select_document)

    sys.exit(app.exec_())
