from PySide6 import QtWidgets

from dangerzone.global_common import GlobalCommon
from dangerzone.gui import Application, GuiCommon


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(
        self, global_common: GlobalCommon, gui_common: GuiCommon, app: Application
    ):
        super(SysTray, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.app = app

        self.setIcon(self.gui_common.get_window_icon())

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
