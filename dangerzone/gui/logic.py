import logging
import os
import pipes
import platform
import shlex
import subprocess
import typing
from pathlib import Path
from typing import Dict, Optional

from colorama import Fore

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

if platform.system() == "Linux":
    from xdg.DesktopEntry import DesktopEntry

from ..isolation_provider.base import IsolationProvider
from ..logic import DangerzoneCore
from ..settings import Settings
from ..util import get_resource_path

log = logging.getLogger(__name__)


class DangerzoneGui(DangerzoneCore):
    """
    Singleton of shared state / functionality for the GUI and core app logic
    """

    def __init__(
        self, app: QtWidgets.QApplication, isolation_provider: IsolationProvider
    ) -> None:
        super().__init__(isolation_provider)

        # Qt app
        self.app = app

        # Only one output dir is supported in the GUI
        self.output_dir: str = ""

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

        # Are we done waiting (for Docker Desktop to be installed, or for container to install)
        self.is_waiting_finished = False

    def get_window_icon(self) -> QtGui.QIcon:
        if platform.system() == "Windows":
            path = get_resource_path("dangerzone.ico")
        else:
            path = get_resource_path("icon.png")
        return QtGui.QIcon(path)

    def open_pdf_viewer(self, filename: str) -> None:
        if platform.system() == "Darwin":
            # Open in Preview
            args = ["open", "-a", "Preview.app", filename]

            # Run
            args_str = " ".join(pipes.quote(s) for s in args)
            log.info(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.run(args)

        elif platform.system() == "Windows":
            os.startfile(Path(filename))  # type: ignore [attr-defined]

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
            log.info(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.Popen(args)

    def _find_pdf_viewers(self) -> Dict[str, str]:
        pdf_viewers: Dict[str, str] = {}
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


class Dialog(QtWidgets.QDialog):
    def __init__(
        self,
        dangerzone: DangerzoneGui,
        title: str,
        ok_text: str = "Ok",
        has_cancel: bool = True,
        cancel_text: str = "Cancel",
        extra_button_text: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.dangerzone = dangerzone

        self.setWindowTitle(title)
        self.setWindowIcon(self.dangerzone.get_window_icon())
        self.setModal(True)

        flags = (
            QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)

        message_layout = self.create_layout()

        ok_button = QtWidgets.QPushButton(ok_text)
        ok_button.clicked.connect(self.clicked_ok)
        if extra_button_text:
            extra_button = QtWidgets.QPushButton(extra_button_text)
            extra_button.clicked.connect(self.clicked_extra)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(ok_button)
        if extra_button_text:
            buttons_layout.addWidget(extra_button)
        if has_cancel:
            cancel_button = QtWidgets.QPushButton(cancel_text)
            cancel_button.clicked.connect(self.clicked_cancel)
            buttons_layout.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(message_layout)
        layout.addSpacing(10)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def create_layout(self) -> QtWidgets.QBoxLayout:
        raise NotImplementedError("Dangerzone dialogs must implement this method")

    def clicked_ok(self) -> None:
        self.done(int(QtWidgets.QDialog.Accepted))

    def clicked_extra(self) -> None:
        self.done(2)

    def clicked_cancel(self) -> None:
        self.done(int(QtWidgets.QDialog.Rejected))

    def launch(self) -> int:
        return self.exec_()


class Alert(Dialog):
    def __init__(  # type: ignore [no-untyped-def]
        self,
        *args,
        message: str = "",
        **kwargs,
    ) -> None:
        self.message = message
        kwargs.setdefault("title", "dangerzone")
        super().__init__(*args, **kwargs)

    def create_layout(self) -> QtWidgets.QBoxLayout:
        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(QtGui.QImage(get_resource_path("icon.png")))
        )

        label = QtWidgets.QLabel()
        label.setText(self.message)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)

        message_layout = QtWidgets.QHBoxLayout()
        message_layout.addWidget(logo)
        message_layout.addSpacing(10)
        message_layout.addWidget(label, stretch=1)

        return message_layout


class CollapsibleBox(QtWidgets.QWidget):
    """Create a widget that can show/hide its contents when you click on it.

    The credits for this code go to eyllanesc's answer in StackOverflow:
    https://stackoverflow.com/a/52617714. We have made the following improvements:

    1. Adapt the code to PySide.
    2. Resize the window once the box uncollapses.
    3. Add type hints.
    """

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None):
        super(CollapsibleBox, self).__init__(parent)
        self.toggle_button = QtWidgets.QToolButton(
            text=title,
            checkable=True,
            checked=False,
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
        self.toggle_button.clicked.connect(self.on_click)

        self.toggle_animation = QtCore.QParallelAnimationGroup(self)

        self.content_area = QtWidgets.QScrollArea(maximumHeight=0, minimumHeight=0)
        self.content_area.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.content_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self, b"minimumHeight")
        )
        self.toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self, b"maximumHeight")
        )
        self.toggle_animation.addAnimation(
            QtCore.QPropertyAnimation(self.content_area, b"maximumHeight")
        )

        self.toggle_animation.finished.connect(self.on_animation_finished)

    def on_click(self) -> None:
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
        )
        self.toggle_animation.setDirection(
            QtCore.QAbstractAnimation.Forward
            if checked
            else QtCore.QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def on_animation_finished(self) -> None:
        if not self.toggle_button.isChecked():
            content_height = self.content_area.layout().sizeHint().height()
            parent = self.parent()
            assert isinstance(parent, QtWidgets.QWidget)
            parent.resize(parent.width(), parent.height() - content_height)

    def setContentLayout(self, layout: QtWidgets.QBoxLayout) -> None:
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = self.sizeHint().height() - self.content_area.maximumHeight()
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            assert isinstance(animation, QtCore.QPropertyAnimation)
            animation.setDuration(60)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(
            self.toggle_animation.animationCount() - 1
        )
        assert isinstance(content_animation, QtCore.QPropertyAnimation)
        content_animation.setDuration(60)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)
