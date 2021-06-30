import os
import sys
import subprocess
import uuid
import pipes
from PySide2 import QtCore


class Vm(QtCore.QObject):
    STATE_OFF = 0
    STATE_STARTING = 1
    STATE_ON = 2
    STATE_STOPPING = 3

    vm_state_change = QtCore.Signal(int)

    def __init__(self, global_common):
        super(Vm, self).__init__()
        self.global_common = global_common

        # VM starts off
        self.state = self.STATE_OFF

        # Hyperkit subprocess
        self.hyperkit_p = None

        # Relevant paths
        self.hyperkit_path = self.global_common.get_resource_path("bin/hyperkit")
        self.vm_iso_path = self.global_common.get_resource_path("vm/dangerzone.iso")
        self.vm_kernel_path = self.global_common.get_resource_path("vm/kernel")
        self.vm_initramfs_path = self.global_common.get_resource_path(
            "vm/initramfs.img"
        )

        # Folder to hold files related to the VM
        self.vm_state_dir = os.path.join(self.global_common.appdata_path, "vm-state")
        os.makedirs(self.vm_state_dir, exist_ok=True)

        # UDID for VM
        self.vm_uuid = str(uuid.uuid4())
        self.vm_cmdline = "modules=virtio_net console=ttyS0"

    def start(self):
        self.state = self.STATE_STARTING
        self.vm_state_change.emit(self.state)

        # Kill existing process
        if self.hyperkit_p is not None:
            self.hyperkit_p.terminate()
            self.hyperkit_p = None

        # Run Hyperkit
        args = [
            self.hyperkit_path,
            "-F",
            os.path.join(self.vm_state_dir, "hyperkit.pid"),
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
            "2:0,virtio-net",
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
            stderr=sys.stderr,
        )

    def restart(self):
        pass

    def stop(self):
        pass
