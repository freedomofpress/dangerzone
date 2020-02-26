from PyQt5 import QtCore, QtWidgets
import os
import sys
import signal
import platform
import click
import time

from .common import Common
from .main_window import MainWindow
from .docker_installer import (
    is_docker_installed,
    is_docker_ready,
    launch_docker_windows,
    DockerInstaller,
)

dangerzone_version = "0.0.1"


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

    # Common object
    common = Common(app)

    # If we're using Linux and docker, see if we need to add the user to the docker group
    if platform.system() == "Linux" and common.container_runtime == "/usr/bin/docker":
        if not common.ensure_user_is_in_docker_group():
            print("Failed to add user to docker group")
            return

    # See if we need to install Docker...
    if (platform.system() == "Darwin" or platform.system() == "Windows") and (
        not is_docker_installed(common) or not is_docker_ready(common)
    ):
        print("Docker is either not installed or not running")
        docker_installer = DockerInstaller(common)
        docker_installer.start()
        return

    windows = []
    doc_opened = False

    # Open a document in a window
    def select_document(filename=None):
        print(f"select_document, filename={filename}")
        new_window = MainWindow(common)

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
            common.set_document_filename(filename)
            new_window.doc_selection_widget.document_selected.emit()

        windows.append(new_window)
        doc_opened = True
        return True

    # If filename is passed as an argument, open it
    if filename is None:
        if platform.system() == "Darwin":
            # Wait 0.5 seconds to see if we can an open document event, and if not open a new window without a document
            def open_window_if_not_already_open():
                if not doc_opened:
                    select_document()

            timer = QtCore.QTimer()
            timer.setSingleShot(True)
            timer.setInterval(500)
            timer.timeout.connect(open_window_if_not_already_open)
            timer.start()
        else:
            # Open a new window without a document
            select_document()
    else:
        # Try opening a window with the docoument selected
        if not select_document(filename):
            return False

    # If we get a file open event, open it
    app.document_selected.connect(select_document)

    sys.exit(app.exec_())
