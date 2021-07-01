#!/usr/bin/env python3
import os
import json
import stat
import subprocess


def main():
    if not os.path.exists("/dev/vda"):
        print("Disk is not mounted, skipping")
        return

    # Read data
    with open("/dev/vda", "rb") as f:
        s = f.read()

    info = json.loads(s[0 : s.find(b"\0")])

    # Create SSH files
    os.makedirs("/home/user/.ssh", mode=0o700, exist_ok=True)
    perms = stat.S_IRUSR | stat.S_IWUSR

    with open("/home/user/.ssh/id_ed25519", "w") as f:
        f.write(info["id_ed25519"])

    with open("/home/user/.ssh/id_ed25519.pub", "w") as f:
        f.write(info["id_ed25519.pub"])

    with open("/home/user/.ssh/authorized_keys", "w") as f:
        f.write(info["id_ed25519.pub"])

    os.chmod("/home/user/.ssh/id_ed25519", perms)
    os.chmod("/home/user/.ssh/id_ed25519.pub", perms)
    os.chmod("/home/user/.ssh/authorized_keys", perms)

    # Start SSH reverse port forward
    subprocess.run(
        [
            "/usr/bin/ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            "/home/user/.ssh/id_ed25519",
            "-N",
            "-R",
            f"{info['tunnel_port']}:127.0.0.1:22",
            "-p",
            info["port"],
            f"{info['user']}@{info['ip']}",
        ]
    )


if __name__ == "__main__":
    main()
