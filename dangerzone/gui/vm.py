import os
import sys
import subprocess
import uuid
import pipes
import tempfile
import socket
import random
import getpass
import json
import psutil
import time
from PySide2 import QtCore


class Vm(QtCore.QObject):
    STATE_OFF = 0
    STATE_STARTING = 1
    STATE_ON = 2
    STATE_FAIL = 3

    vm_state_change = QtCore.Signal(int)

    def __init__(self, global_common):
        super(Vm, self).__init__()
        self.global_common = global_common

        # VM starts off
        self.state = self.STATE_OFF

        # Ports for ssh services
        self.sshd_port = None
        self.sshd_tunnel_port = None

        # Processes
        self.vpnkit_p = None
        self.hyperkit_p = None
        self.sshd_pid = None

        # Relevant paths
        self.vpnkit_path = self.global_common.get_resource_path("bin/vpnkit")
        self.hyperkit_path = self.global_common.get_resource_path("bin/hyperkit")
        self.vm_iso_path = self.global_common.get_resource_path("vm/dangerzone.iso")
        self.vm_kernel_path = self.global_common.get_resource_path("vm/kernel")
        self.vm_initramfs_path = self.global_common.get_resource_path(
            "vm/initramfs.img"
        )

        # Folder to hold temporary files related to the VM
        self.state_dir = tempfile.TemporaryDirectory()
        self.vpnkit_sock_path = os.path.join(self.state_dir.name, "vpnkit.eth.sock")
        self.hyperkit_pid_path = os.path.join(self.state_dir.name, "hyperkit.pid")
        self.ssh_host_key_path = os.path.join(self.state_dir.name, "host_ed25519")
        self.ssh_host_pubkey_path = os.path.join(
            self.state_dir.name, "host_ed25519.pub"
        )
        self.ssh_client_key_path = os.path.join(self.state_dir.name, "client_ed25519")
        self.ssh_client_pubkey_path = os.path.join(
            self.state_dir.name, "client_ed25519.pub"
        )
        self.sshd_pid_path = os.path.join(self.state_dir.name, "sshd.pid")
        self.sshd_log_path = os.path.join(self.state_dir.name, "sshd.log")
        self.vm_disk_img_path = os.path.join(self.state_dir.name, "disk.img")

        # UDID for VM
        self.vm_uuid = str(uuid.uuid4())
        self.vm_cmdline = (
            "earlyprintk=serial console=ttyS0 modules=loop,squashfs,sd-mod"
        )

        # Threads
        self.wait_t = None

    def __del__(self):
        self.stop()

    def start(self):
        self.state = self.STATE_STARTING
        self.vm_state_change.emit(self.state)

        # Delete keys if they already exist
        for filename in [
            self.ssh_host_key_path,
            self.ssh_host_pubkey_path,
            self.ssh_client_key_path,
            self.ssh_client_pubkey_path,
        ]:
            if os.path.exists(filename):
                os.remove(filename)

        # Generate new keys
        subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-t",
                "ed25519",
                "-C",
                "dangerzone-host",
                "-N",
                "",
                "-f",
                self.ssh_host_key_path,
            ]
        )
        subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-t",
                "ed25519",
                "-C",
                "dangerzone-client",
                "-N",
                "",
                "-f",
                self.ssh_client_key_path,
            ]
        )
        with open(self.ssh_client_key_path) as f:
            ssh_client_key = f.read()
        with open(self.ssh_client_pubkey_path) as f:
            ssh_client_pubkey = f.read()

        # Find an open port
        self.sshd_port = self.find_open_port()
        self.sshd_tunnel_port = self.find_open_port()

        # Start an sshd service on this port
        args = [
            "/usr/sbin/sshd",
            "-4",
            "-E",
            self.sshd_log_path,
            "-o",
            f"PidFile={self.sshd_pid_path}",
            "-o",
            f"HostKey={self.ssh_host_key_path}",
            "-o",
            f"ListenAddress=127.0.0.1:{self.sshd_port}",
            "-o",
            f"AllowUsers={getpass.getuser()}",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "PubkeyAuthentication=yes",
            "-o",
            "Compression=yes",
            "-o",
            "ForceCommand=/usr/bin/whoami",
            "-o",
            "UseDNS=no",
            "-o",
            f"AuthorizedKeysFile={self.ssh_client_pubkey_path}",
        ]
        args_str = " ".join(pipes.quote(s) for s in args)
        print("> " + args_str)
        subprocess.run(args)

        # Create a JSON object to pass into the VM
        # This is a 512kb file that starts with a JSON object, followed by null bytes
        vm_info = {
            "id_ed25519": ssh_client_key,
            "id_ed25519.pub": ssh_client_pubkey,
            "user": getpass.getuser(),
            "ip": "192.168.65.2",
            "port": self.sshd_port,
            "tunnel_port": self.sshd_tunnel_port,
        }
        with open(self.vm_disk_img_path, "wb") as f:
            vm_info_bytes = json.dumps(vm_info).encode()
            f.write(vm_info_bytes)
            f.write(b"\x00" * (512 * 1024 - len(vm_info_bytes)))

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
        self.vpnkit_p = subprocess.Popen(args)

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
            "-s",
            f"3:0,virtio-blk,{self.vm_disk_img_path}",
            "-U",
            self.vm_uuid,
            "-f",
            f'kexec,{self.vm_kernel_path},{self.vm_initramfs_path},"{self.vm_cmdline}"',
        ]
        args_str = " ".join(pipes.quote(s) for s in args)
        print("> " + args_str)
        self.hyperkit_p = subprocess.Popen(
            args,
            # stdout=sys.stdout,
            # stderr=subprocess.STDOUT,
        )

        # Get the sshd PID
        with open(self.sshd_pid_path) as f:
            self.sshd_pid = int(f.read())

        print(f"sshd PID: {self.sshd_pid}")
        print(f"vpnkit PID: {self.vpnkit_p.pid}")
        print(f"hyperkit PID: {self.hyperkit_p.pid}")

        # Wait for SSH thread
        self.wait_t = WaitForSsh(self.sshd_tunnel_port)
        self.wait_t.connected.connect(self.vm_connected)
        self.wait_t.timeout.connect(self.vm_timeout)
        self.wait_t.start()

    def vm_connected(self):
        self.state = self.STATE_ON
        self.vm_state_change.emit()

    def vm_timeout(self):
        self.state = self.STATE_FAIL
        self.vm_state_change.emit()

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        # Kill existing processes
        self.kill_sshd()
        if self.vpnkit_p is not None:
            self.vpnkit_p.terminate()
            self.vpnkit_p = None
        if self.hyperkit_p is not None:
            self.hyperkit_p.terminate()
            self.hyperkit_p = None

    def find_open_port(self):
        with socket.socket() as tmpsock:
            while True:
                try:
                    tmpsock.bind(("127.0.0.1", random.randint(1024, 65535)))
                    break
                except OSError:
                    pass
            _, port = tmpsock.getsockname()

        return port

    def kill_sshd(self):
        if self.sshd_pid and psutil.pid_exists(self.sshd_pid):
            try:
                proc = psutil.Process(self.sshd_pid)
                proc.kill()
            except Exception:
                pass

        self.sshd_pid = None


class WaitForSsh(QtCore.QThread):
    connected = QtCore.Signal()
    timeout = QtCore.Signal()

    def __init__(self, ssh_port):
        super(WaitForSsh, self).__init__()
        self.ssh_port = ssh_port

    def run(self):
        # Wait for the SSH port to be open
        timeout_seconds = 45
        sock = socket.socket()
        sock.settimeout(timeout_seconds)
        try:
            sock.connect(("127.0.0.1", int(self.ssh_port)))
            self.connected.emit()
            sock.close()
        except socket.timeout:
            self.timeout.emit()
