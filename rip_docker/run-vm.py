#!/usr/bin/env python3
import subprocess
import uuid
import os


def main():
    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vm"
    )

    vm_uuid = uuid.uuid4()

    cmd = [
        "hyperkit",
        "-m",
        "4G",
        "-c",
        "2",
        "-s",
        "0:0,hostbridge",
        "-s",
        "31,lpc",
        "-s",
        "2:0,virtio-net",
        "-l",
        "com1,stdio",
        # "-F",
        # os.path.join(base_dir, "hyperkit.pid"),
        "-U",
        str(vm_uuid),
        "-s",
        "3:0,ahci-cd," + os.path.join(base_dir, "alpine-dangerzone-v3.14-x86_64.iso"),
        "-f",
        "kexec,"
        + os.path.join(base_dir, "vmlinuz-virt")
        + ","
        + os.path.join(base_dir, "initramfs-virt")
        + ',"modules=virtio_net console=ttyS0"',
    ]
    print(" ".join(cmd))

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
