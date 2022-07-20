import platform

from PySide2 import QtWidgets


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, global_common, gui_common, app, app_wrapper):
        super(SysTray, self).__init__()
        self.global_common = global_common
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

    def new_window(self):
        self.app_wrapper.new_window.emit()

    def quit_clicked(self):
        self.app.quit()
