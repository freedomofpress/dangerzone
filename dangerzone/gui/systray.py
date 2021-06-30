import os
from PySide2 import QtWidgets


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

        # Dangerzone VM
        self.vpnkit_p = None
        self.hyperkit_p = None
        self.hyperkit_path = self.global_common.get_resource_path("bin/hyperkit")
        self.vpnkit_path = self.global_common.get_resource_path("bin/vpnkit")
        self.vm_iso_path = self.global_common.get_resource_path(
            "vm/alpine-dangerzone-v3.14-x86_64.iso"
        )
        self.vm_kernel_path = self.global_common.get_resource_path("vm/vmlinuz-virt")
        self.vm_initramfs_path = self.global_common.get_resource_path(
            "vm/initramfs-virt"
        )
        self.vm_state_dir = os.path.join(self.global_common.appdata_path, "vm-state")
        os.makedirs(self.vm_state_dir, exist_ok=True)
        self.vm_start()

    def vm_start(self):
        self.status_action.setText("Starting Dangerzone ...")

        # Kill existing processes
        if self.vpnkit_p is not None:
            self.vpnkit_p.terminate()
        if self.hyperkit_p is not None:
            self.hyperkit_p.terminate()

        # Run VPNKit

        # Run Hyperkit

    def restart_clicked(self):
        self.status_action.setText("Restarting Dangerzone ...")

    def quit_clicked(self):
        self.app.quit()
