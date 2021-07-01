#!/usr/bin/env python3
import os
import json
import subprocess
import shutil


def main():
    if not os.path.exists("/dev/vda"):
        print("Disk is not mounted, skipping")
        return

    # Read data
    with open("/dev/vda", "rb") as f:
        s = f.read()

    info = json.loads(s[0 : s.find(b"\0")])

    # Create SSH files
    os.makedirs("/home/user/.ssh", exist_ok=True)

    with open("/home/user/.ssh/id_ed25519", "w") as f:
        f.write(info["id_ed25519"])
        f.write("\n")

    with open("/home/user/.ssh/id_ed25519.pub", "w") as f:
        f.write(info["id_ed25519.pub"])
        f.write("\n")

    with open("/home/user/.ssh/authorized_keys", "w") as f:
        f.write(info["id_ed25519.pub"])
        f.write("\n")

    with open("/home/user/.ssh/config", "w") as f:
        f.write("Host hostbox\n")
        f.write(f"  Hostname {info['ip']}\n")
        f.write(f"  Port {info['port']}\n")
        f.write(f"  User {info['user']}\n")
        f.write("  IdentityFile /home/user/.ssh/id_ed25519\n")
        f.write("\n")

    os.chmod("/home/user/.ssh", 0o700)
    os.chmod("/home/user/.ssh/id_ed25519", 0o600)
    os.chmod("/home/user/.ssh/id_ed25519.pub", 0o644)
    os.chmod("/home/user/.ssh/authorized_keys", 0o600)
    os.chmod("/home/user/.ssh/config", 0o600)

    shutil.chown("/home/user/.ssh", "user", "user")
    shutil.chown("/home/user/.ssh/id_ed25519", "user", "user")
    shutil.chown("/home/user/.ssh/id_ed25519.pub", "user", "user")
    shutil.chown("/home/user/.ssh/authorized_keys", "user", "user")
    shutil.chown("/home/user/.ssh/config", "user", "user")

    # Start SSH reverse port forward
    subprocess.run(
        [
            "/usr/bin/sudo",
            "-u",
            "user",
            "/usr/bin/ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-N",
            "-R",
            f"{info['tunnel_port']}:127.0.0.1:22",
            "hostbox",
        ]
    )


if __name__ == "__main__":
    main()
