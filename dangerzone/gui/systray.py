import platform
from typing import TYPE_CHECKING

from PySide2 import QtWidgets

from .logic import DangerzoneGui


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(
        self,
        dangerzone: DangerzoneGui,
        app: QtWidgets.QApplication,
    ) -> None:
        super(SysTray, self).__init__()
        self.dangerzone = dangerzone
        self.app = app

        self.setIcon(self.dangerzone.get_window_icon())

        menu = QtWidgets.QMenu()

        self.new_action = menu.addAction("New window")
        self.new_action.triggered.connect(self.new_window)

        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

    def new_window(self) -> None:
        self.new_window.emit()

    def quit_clicked(self) -> None:
        self.app.quit()
