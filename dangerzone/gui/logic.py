from __future__ import annotations

import logging
import os
import platform
import shlex
import subprocess
import typing
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

from colorama import Fore

from ..container_utils import subprocess_run

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets

    from . import Application
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

if platform.system() == "Linux":
    from xdg.DesktopEntry import DesktopEntry, ParsingError

from ..isolation_provider.base import IsolationProvider
from ..logic import DangerzoneCore
from ..util import get_resource_path, replace_control_chars

log = logging.getLogger(__name__)


class DangerzoneGui(DangerzoneCore):
    """
    Singleton of shared state / functionality for the GUI and core app logic
    """

    def __init__(
        self, app: "Application", isolation_provider: IsolationProvider
    ) -> None:
        super().__init__(isolation_provider)

        # Qt app
        self.app = app

        # Only one output dir is supported in the GUI
        self.output_dir: str = ""

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # Preload ordered list of PDF viewers on computer, starting with default
        self.pdf_viewers = self._find_pdf_viewers()

        # Are we done waiting (for Docker Desktop to be installed, or for container to install)
        self.is_waiting_finished = False

    def get_window_icon(self) -> QtGui.QIcon:
        if platform.system() == "Windows":
            path = get_resource_path("dangerzone.ico")
        else:
            path = get_resource_path("icon.png")
        return QtGui.QIcon(str(path))

    def open_pdf_viewer(self, filename: str) -> None:
        if platform.system() == "Darwin":
            # Open in Preview
            args = ["open", "-a", "Preview.app", filename]

            # Run
            args_str = replace_control_chars(" ".join(shlex.quote(s) for s in args))
            log.info(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess_run(args)

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
            args_str = replace_control_chars(" ".join(shlex.quote(s) for s in args))
            log.info(Fore.YELLOW + "> " + Fore.CYAN + args_str)
            subprocess.Popen(args)

    def _find_pdf_viewers(self) -> OrderedDict[str, str]:
        pdf_viewers: OrderedDict[str, str] = OrderedDict()
        if platform.system() == "Linux":
            # Opportunistically query for default pdf handler
            default_pdf_viewer = None
            try:
                default_pdf_viewer = subprocess.check_output(
                    ["xdg-mime", "query", "default", "application/pdf"]
                ).decode()
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                # Log it and continue
                log.info(
                    "xdg-mime query failed, default PDF handler could not be found."
                )
                log.debug(f"xdg-mime query failed: {e}")

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
                            try:
                                desktop_entry = DesktopEntry(full_filename)
                            except ParsingError:
                                # Do not stop when encountering malformed desktop entries
                                continue
                            except Exception:
                                log.exception(
                                    "Encountered the following exception while processing desktop entry %s",
                                    full_filename,
                                )
                            else:
                                desktop_entry_name = desktop_entry.getName()
                                if (
                                    "application/pdf" in desktop_entry.getMimeTypes()
                                    and "dangerzone" not in desktop_entry_name.lower()
                                ):
                                    pdf_viewers[desktop_entry_name] = (
                                        desktop_entry.getExec()
                                    )

                                    # Put the default entry first
                                    if filename == default_pdf_viewer:
                                        try:
                                            pdf_viewers.move_to_end(
                                                desktop_entry_name, last=False
                                            )
                                        except KeyError as e:
                                            # Should be unreachable
                                            log.error(
                                                f"Problem reordering applications: {e}"
                                            )
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
        checkbox_text: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.dangerzone = dangerzone
        self.setProperty("OSColorMode", self.dangerzone.app.os_color_mode.value)

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

        self.ok_button = QtWidgets.QPushButton(ok_text)
        self.ok_button.clicked.connect(self.clicked_ok)

        self.extra_button: Optional[QtWidgets.QPushButton] = None
        if extra_button_text:
            self.extra_button = QtWidgets.QPushButton(extra_button_text)
            self.extra_button.clicked.connect(self.clicked_extra)

        self.cancel_button: Optional[QtWidgets.QPushButton] = None
        if has_cancel:
            self.cancel_button = QtWidgets.QPushButton(cancel_text)
            self.cancel_button.clicked.connect(self.clicked_cancel)

        self.checkbox: Optional[QtWidgets.QCheckBox] = None
        if checkbox_text:
            self.checkbox = QtWidgets.QCheckBox(checkbox_text)

        buttons_layout = self.create_buttons_layout()

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(message_layout)
        layout.addSpacing(10)
        layout.addLayout(buttons_layout)
        if self.checkbox:
            layout.addSpacing(10)
            layout.addWidget(self.checkbox)
        self.setLayout(layout)

    def create_buttons_layout(self) -> QtWidgets.QHBoxLayout:
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()

        buttons_layout.addWidget(self.ok_button)
        if self.extra_button:
            buttons_layout.addWidget(self.extra_button)
        if self.cancel_button:
            buttons_layout.addWidget(self.cancel_button)

        return buttons_layout

    def create_layout(self) -> QtWidgets.QBoxLayout:
        raise NotImplementedError("Dangerzone dialogs must implement this method")

    def clicked_ok(self) -> None:
        self.done(int(QtWidgets.QDialog.Accepted))

    def clicked_extra(self) -> None:
        self.done(2)

    def clicked_cancel(self) -> None:
        self.done(int(QtWidgets.QDialog.Rejected))

    def launch(self) -> int:
        return self.exec()


class Alert(Dialog):
    def __init__(
        self,
        *args: Any,
        message: str = "",
        **kwargs: Any,
    ) -> None:
        self.message = message
        kwargs.setdefault("title", "dangerzone")
        super().__init__(*args, **kwargs)

    def create_layout(self) -> QtWidgets.QBoxLayout:
        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(QtGui.QImage(str(get_resource_path("icon.png"))))
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


class UpdateDialog(Dialog):
    def __init__(  # type: ignore [no-untyped-def]
        self,
        *args,
        intro_msg: Optional[str] = None,
        middle_widget: Optional[QtWidgets.QWidget] = None,
        epilogue_msg: Optional[str] = None,
        **kwargs,
    ) -> None:
        self.intro_msg = intro_msg
        self.middle_widget = middle_widget
        self.epilogue_msg = epilogue_msg
        super().__init__(*args, **kwargs)

    def create_layout(self) -> QtWidgets.QBoxLayout:
        self.setMinimumWidth(500)
        message_layout = QtWidgets.QVBoxLayout()

        if self.intro_msg is not None:
            intro = QtWidgets.QLabel()
            intro.setText(self.intro_msg)
            intro.setWordWrap(True)
            intro.setAlignment(QtCore.Qt.AlignCenter)
            intro.setOpenExternalLinks(True)
            message_layout.addWidget(intro)
            message_layout.addSpacing(10)

        if self.middle_widget is not None:
            self.middle_widget.setParent(self)
            message_layout.addWidget(self.middle_widget)
            message_layout.addSpacing(10)

        if self.epilogue_msg is not None:
            epilogue = QtWidgets.QLabel()
            epilogue.setText(self.epilogue_msg)
            epilogue.setWordWrap(True)
            epilogue.setOpenExternalLinks(True)
            message_layout.addWidget(epilogue)
            message_layout.addSpacing(10)

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
