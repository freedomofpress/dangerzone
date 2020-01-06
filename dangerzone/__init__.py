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

    # If a filename wasn't passed in, get with with a dialog
    if filename == "":
        filename = QtWidgets.QFileDialog.getOpenFileName(
            main_window,
            "Open document",
            filter="Documents (*.pdf *.docx *.doc *.xlsx *.xls *.pptx *.ppt *.odt *.fodt *.ods *.fods *.odp *.fodp *.odg *.fodg *.odf)",
        )
        if filename[0] == "":
            print("No document was not selected")
            return

        filename = filename[0]
    else:
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

    main_window.start(filename)
    sys.exit(app.exec_())
