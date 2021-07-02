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

        if platform.system() == "Darwin":
            self.status_action = menu.addAction("...")
            self.status_action.setEnabled(False)
            menu.addSeparator()

        self.new_action = menu.addAction("New window")
        self.new_action.triggered.connect(self.new_window)

        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

        if self.global_common.vm:
            self.global_common.vm.vm_state_change.connect(self.vm_state_change)

    def vm_state_change(self, state):
        if state == self.global_common.vm.STATE_OFF:
            self.status_action.setText("Dangerzone VM is off")
        elif state == self.global_common.vm.STATE_STARTING:
            self.status_action.setText("Dangerzone VM is starting...")
        elif state == self.global_common.vm.STATE_ON:
            self.status_action.setText("Dangerzone VM is running")
        elif state == self.global_common.vm.STATE_FAIL:
            self.status_action.setText("Dangerzone VM failed to start")

    def new_window(self):
        self.app_wrapper.new_window.emit()

    def quit_clicked(self):
        self.app.quit()
