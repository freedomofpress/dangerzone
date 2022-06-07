import os
import platform
import subprocess
import shlex
import pipes
from PySide6 import QtGui
from colorama import Fore

from dangerzone.gui import Application
from dangerzone.gui.settings import Settings

if platform.system() == "Linux":
    from xdg.DesktopEntry import DesktopEntry  # type: ignore


class GuiCommon(object):
    """
    The GuiCommon class is a singleton of shared functionality for the GUI
    """

    def __init__(self, app: Application):
        # Qt app
        self.app = app

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

        # Are we done waiting (for Docker Desktop to be installed, or for container to install)
        self.is_waiting_finished = False

        self.settings = Settings()

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
