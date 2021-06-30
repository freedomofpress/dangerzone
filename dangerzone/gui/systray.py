from PySide2 import QtCore, QtGui, QtWidgets


class SysTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, global_common, gui_common, app):
        super(SysTray, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.app = app

        self.setIcon(self.gui_common.get_window_icon())

        menu = QtWidgets.QMenu()
        self.status_action = menu.addAction("...")
        self.status_action.setEnabled(False)
        menu.addSeparator()
        self.restart_action = menu.addAction("Restart")
        self.restart_action.triggered.connect(self.restart_clicked)
        self.quit_action = menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_clicked)

        self.setContextMenu(menu)
        self.show()

        # Processes for the Dangerzone VM
        self.vpnkit_p = None
        self.hyperkit_p = None

        # Start the VM
        self.vm_start()

    def vm_start(self):
        self.status_action.setText("Starting Dangerzone ...")

        # Kill existing processes
        if self.vpnkit_p is not None:
            self.vpnkit_p.terminate()
        if self.hyperkit_p is not None:
            self.hyperkit_p.terminate()

    def restart_clicked(self):
        self.status_action.setText("Restarting Dangerzone ...")

    def quit_clicked(self):
        self.app.quit()
