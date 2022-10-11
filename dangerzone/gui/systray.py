import platform
from typing import TYPE_CHECKING

from PySide2 import QtWidgets

from ..logic import DangerzoneCore
from .logic import DangerzoneGui

if TYPE_CHECKING:
    from . import ApplicationWrapper


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(
        self,
        dangerzone: DangerzoneCore,
        gui_common: DangerzoneGui,
        app: QtWidgets.QApplication,
        app_wrapper: "ApplicationWrapper",
    ) -> None:
        super(SysTray, self).__init__()
        self.dangerzone = dangerzone
        self.gui_common = gui_common
        self.app = app
        self.app_wrapper = app_wrapper

        self.setIcon(self.gui_common.get_window_icon())

        menu = QtWidgets.QMenu()

        self.new_action = menu.addAction("New window")
        self.new_action.triggered.connect(self.new_window)

        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

    def new_window(self) -> None:
        self.app_wrapper.new_window.emit()

    def quit_clicked(self) -> None:
        self.app.quit()
