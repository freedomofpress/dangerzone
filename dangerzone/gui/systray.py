from PySide6 import QtWidgets
from PySide6.QtGui import QIcon

from dangerzone.gui import GuiCommon, Application
import dangerzone.util as dzutil


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, common: GuiCommon, app: Application):
        super(SysTray, self).__init__()
        self.common = common
        self.app = app

        self.setIcon(QIcon(dzutil.WINDOW_ICON_PATH))

        menu = QtWidgets.QMenu()

        self.new_action = menu.addAction("New window")
        self.new_action.triggered.connect(self.new_window)

        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

    def new_window(self):
        self.app.new_window.emit()

    def quit_clicked(self):
        self.app.quit()
