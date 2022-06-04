import os
import platform
import subprocess
import shlex
import pipes
from PySide6 import QtCore, QtGui, QtWidgets
from colorama import Fore

from . import Application
from ..global_common import GlobalCommon

if platform.system() == "Darwin":
    import plistlib

elif platform.system() == "Linux":
    import grp
    import getpass
    from xdg.DesktopEntry import DesktopEntry  # type: ignore


class GuiCommon(object):
    """
    The GuiCommon class is a singleton of shared functionality for the GUI
    """

    def __init__(self, app: Application, global_common: GlobalCommon):
        # Qt app
        self.app = app

        # Global common singleton
        self.global_common = global_common

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

        # Are we done waiting (for Docker Desktop to be installed, or for container to install)
        self.is_waiting_finished = False

    @staticmethod
    def get_window_icon():
        if platform.system() == "Windows":
            path = GlobalCommon.get_resource_path("dangerzone.ico")
        else:
            path = GlobalCommon.get_resource_path("icon.png")
        return QtGui.QIcon(path)

    def open_pdf_viewer(self, filename: str):
        if platform.system() == "Darwin":
            # Open in Preview
            args = ["open", "-a", "Preview.app", filename]

            # Run
            args_str = " ".join(pipes.quote(s) for s in args)
            print(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.run(args)

        elif platform.system() == "Linux":
            # Get the PDF reader command
            args = shlex.split(
                self.pdf_viewers[self.global_common.settings.get("open_app")]
            )
            # %f, %F, %u, and %U are filenames or URLS -- so replace with the file to open
            for i in range(len(args)):
                if (
                    args[i] == "%f"
                    or args[i] == "%F"
                    or args[i] == "%u"
                    or args[i] == "%U"
                ):
                    args[i] = filename

            # Open as a background process
            args_str = " ".join(pipes.quote(s) for s in args)
            print(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.Popen(args)

    @staticmethod
    def _find_pdf_viewers():
        """Dict of PDF viewers installed on the machine, empty if system is not Linux."""
        pdf_viewers = {}
        if platform.system() == "Linux":
            # Find all .desktop files
            for search_path in [
                "/usr/share/applications",
                "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
            ]:
                try:
                    for filename in os.listdir(search_path):
                        full_filename = os.path.join(search_path, filename)
                        if os.path.splitext(filename)[1] == ".desktop":

                            # See which ones can open PDFs
                            desktop_entry = DesktopEntry(full_filename)
                            if (
                                "application/pdf" in desktop_entry.getMimeTypes()
                                and desktop_entry.getName() != "dangerzone"
                            ):
                                pdf_viewers[
                                    desktop_entry.getName()
                                ] = desktop_entry.getExec()

                except FileNotFoundError:
                    pass

        return pdf_viewers


class Alert(QtWidgets.QDialog):
    def __init__(
        self,
        message: str,
        ok_text="Ok",
        extra_button_text=None,
    ):
        super(Alert, self).__init__()
        self.setWindowTitle("dangerzone")
        self.setWindowIcon(GuiCommon.get_window_icon())
        self.setModal(True)

        flags = (  # TODO Mypy: unsupported left operand type for | ("WindowType")
            QtCore.Qt.CustomizeWindowHint  # type: ignore
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)

        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(
                QtGui.QImage(GlobalCommon.get_resource_path("icon.png"))
            )
        )

        label = QtWidgets.QLabel()
        label.setText(message)
        label.setWordWrap(True)

        message_layout = QtWidgets.QHBoxLayout()
        message_layout.addWidget(logo)
        message_layout.addSpacing(10)
        message_layout.addWidget(label, stretch=1)

        ok_button = QtWidgets.QPushButton(ok_text)
        ok_button.clicked.connect(self.clicked_ok)
        if extra_button_text:
            extra_button = QtWidgets.QPushButton(extra_button_text)
            extra_button.clicked.connect(self.clicked_extra)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.clicked_cancel)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(ok_button)
        if extra_button_text:
            buttons_layout.addWidget(extra_button)
        buttons_layout.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(message_layout)
        layout.addSpacing(10)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def clicked_ok(self):
        self.done(QtWidgets.QDialog.Accepted)

    def clicked_extra(self):
        self.done(2)

    def clicked_cancel(self):
        self.done(QtWidgets.QDialog.Rejected)

    def launch(self):
        return self.exec_()
