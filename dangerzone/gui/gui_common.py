import os
import platform
import subprocess
import shlex
import pipes
from PySide6 import QtGui
from colorama import Fore  # type: ignore

from dangerzone.common import Common
from dangerzone.gui import Application
from dangerzone.gui.settings import Settings

if platform.system() == "Linux":
    import xdg


class GuiCommon(Common):
    """
    The GuiCommon class adds GUI-specific features to Common
    """

    def __init__(self, app: Application):
        super().__init__()

        # Qt app
        self.app = app
        self.settings = Settings()

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

        # Are we done waiting (for Docker Desktop to be installed, or for container to install)
        self.is_waiting_finished = False

    def open_pdf_viewer(self, filename: str):
        if platform.system() == "Darwin":
            # Open in Preview
            args = ["open", "-a", "Preview.app", filename]
            args_str = " ".join(pipes.quote(s) for s in args)
            print(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.run(args)
        elif platform.system() == "Linux":
            # Get the PDF reader command
            args = shlex.split(self.pdf_viewers[self.settings.get("open_app")])
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
    def _find_pdf_viewers() -> dict[str, str]:
        """Dict of PDF viewers installed on the machine, empty if system is not Linux."""
        pdf_viewers: dict[str, str] = {}
        if platform.system() == "Linux":
            # Find all .desktop files
            paths = [path + "/applications" for path in xdg.BaseDirectory.xdg_data_dirs]
            for path in paths:
                try:  # search the directory
                    contents = os.listdir(path)
                except FileNotFoundError:
                    pass
                else:
                    for file_name in contents:
                        if os.path.splitext(file_name)[1] == ".desktop":
                            # See which ones can open PDFs
                            file_path = os.path.join(path, file_name)
                            entry = xdg.DesktopEntry(file_path)
                            if "application/pdf" in entry.getMimeTypes() and entry.getName() != "dangerzone":
                                pdf_viewers[entry.getName()] = entry.getExec()
        return pdf_viewers
