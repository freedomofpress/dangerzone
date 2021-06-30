import os
import sys
import subprocess
import uuid
import pipes
import tempfile
from PySide2 import QtCore


class Vm(QtCore.QObject):
    STATE_OFF = 0
    STATE_STARTING = 1
    STATE_ON = 2

    vm_state_change = QtCore.Signal(int)

    def __init__(self, global_common):
        super(Vm, self).__init__()
        self.global_common = global_common

        # VM starts off
        self.state = self.STATE_OFF

        # Processes
        self.vpnkit_p = None
        self.hyperkit_p = None

        # Relevant paths
        self.vpnkit_path = self.global_common.get_resource_path("bin/vpnkit")
        self.hyperkit_path = self.global_common.get_resource_path("bin/hyperkit")
        self.vm_iso_path = self.global_common.get_resource_path("vm/dangerzone.iso")
        self.vm_kernel_path = self.global_common.get_resource_path("vm/kernel")
        self.vm_initramfs_path = self.global_common.get_resource_path(
            "vm/initramfs.img"
        )

        # Folder to hold files related to the VM
        self.state_dir = tempfile.TemporaryDirectory()
        self.vpnkit_sock_path = os.path.join(self.state_dir.name, "vpnkit.eth.sock")
        self.hyperkit_pid_path = os.path.join(self.state_dir.name, "hyperkit.pid")

        # UDID for VM
        self.vm_uuid = str(uuid.uuid4())
        self.vm_cmdline = (
            "earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod"
        )

    def start(self):
        self.state = self.STATE_STARTING
        self.vm_state_change.emit(self.state)

        # Run VPNKit
        args = [
            self.vpnkit_path,
            "--ethernet",
            self.vpnkit_sock_path,
            "--gateway-ip",
            "192.168.65.1",
            "--host-ip",
            "192.168.65.2",
            "--lowest-ip",
            "192.168.65.3",
            "--highest-ip",
            "192.168.65.254",
        ]
        args_str = " ".join(pipes.quote(s) for s in args)
        print("> " + args_str)
        self.vpnkit_p = subprocess.Popen(
            args,
            stdout=sys.stdout,
            stderr=subprocess.STDOUT,
        )

        # Run Hyperkit
        args = [
            self.hyperkit_path,
            "-F",
            self.hyperkit_pid_path,
            "-A",
            "-u",
            "-m",
            "4G",
            "-c",
            "2",
            "-s",
            "0:0,hostbridge",
            "-s",
            "31,lpc",
            "-l",
            "com1,stdio",
            "-s",
            f"1:0,ahci-cd,{self.vm_iso_path}",
            "-s",
            f"2:0,virtio-vpnkit,path={self.vpnkit_sock_path}",
            "-U",
            self.vm_uuid,
            "-f",
            f'kexec,{self.vm_kernel_path},{self.vm_initramfs_path},"{self.vm_cmdline}"',
        ]
        args_str = " ".join(pipes.quote(s) for s in args)
        print("> " + args_str)
        self.hyperkit_p = subprocess.Popen(
            args,
            stdout=sys.stdout,
            stderr=subprocess.STDOUT,
        )

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        # Kill existing processes
        if self.vpnkit_p is not None:
            self.vpnkit_p.terminate()
            self.vpnkit_p = None
        if self.hyperkit_p is not None:
            self.hyperkit_p.terminate()
            self.hyperkit_p = None
