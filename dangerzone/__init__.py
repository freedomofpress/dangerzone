from PyQt5 import QtCore, QtWidgets
import os
import sys
import signal
import click

from .common import Common
from .main_window import MainWindow

dangerzone_version = "0.1.0"


@click.command()
@click.option("--filename", default="", help="Document filename")
def main(filename):
    print(f"dangerzone {dangerzone_version}")

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create the Qt app
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Common object
    common = Common()

    # Main window
    main_window = MainWindow(app, common)

    if filename != "":
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
