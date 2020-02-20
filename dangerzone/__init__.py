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

dangerzone_version = "0.1.0"


@click.command()
@click.argument("filename", required=False)
def main(filename):
    print(f"dangerzone {dangerzone_version}")

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create the Qt app
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Common object
    common = Common(app)

    # See if we need to install Docker...
    if platform.system() == "Darwin" and (
        not is_docker_installed(common) or not is_docker_ready(common)
    ):
        print("Docker is either not installed or not running")
        docker_installer = DockerInstaller(common)
        if docker_installer.start():
            # When installer finished, wait up to 20 minutes for the user to launch it
            for i in range(120):
                if is_docker_installed(common) and is_docker_ready(common):
                    main(filename)
                    return

                print("Waiting for docker to be available ...")
                time.sleep(1)

            # Give up
            print("Docker not available, giving up")

        return

    if platform.system() == "Windows":
        if not is_docker_installed(common):
            print("Docker is not installed")
            docker_installer = DockerInstaller(common)
            docker_installer.start()
            # Quit after the installer runs, because it requires rebooting
            return

        if not is_docker_ready(common):
            print("Docker is not running")
            launch_docker_windows(common)

            # Wait up to 20 minutes for docker to be ready
            for i in range(120):
                if is_docker_ready(common):
                    main(filename)
                    return

                print("Waiting for docker to be available ...")
                time.sleep(1)

            # Give up
            print("Docker not available, giving up")

    # Main window
    main_window = MainWindow(common)

    if filename is not None:
        # Validate filename
        filename = os.path.abspath(os.path.expanduser(filename))
        try:
            open(filename, "rb")
        except FileNotFoundError:
            print("File not found")
            return
        except PermissionError:
            print("Permission denied")
            return
        common.set_document_filename(filename)
        main_window.doc_selection_widget.document_selected.emit()

    sys.exit(app.exec_())
