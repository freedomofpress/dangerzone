import platform
from PySide2 import QtWidgets


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, global_common, gui_common, app):
        super(SysTray, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.app = app

        self.setIcon(self.gui_common.get_window_icon())

        menu = QtWidgets.QMenu()

        if platform.system() == "Darwin":
            self.status_action = menu.addAction("...")
            self.status_action.setEnabled(False)
            menu.addSeparator()
            self.restart_action = menu.addAction("Restart")
            self.restart_action.triggered.connect(self.restart_clicked)

        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

        if self.global_common.vm:
            self.global_common.vm.vm_state_change.connect(self.vm_state_change)

    def vm_state_change(self, state):
        if state == self.global_common.vm.STATE_OFF:
            self.status_action.setText("Dangerzone VM is off")
            self.restart_action.setEnabled(True)
        elif state == self.global_common.vm.STATE_STARTING:
            self.status_action.setText("Dangerzone VM is starting...")
            self.restart_action.setEnabled(False)
        elif state == self.global_common.vm.STATE_ON:
            self.status_action.setText("Dangerzone VM is running")
            self.restart_action.setEnabled(True)

    def restart_clicked(self):
        self.global_common.vm.restart()

    def quit_clicked(self):
        self.app.quit()
