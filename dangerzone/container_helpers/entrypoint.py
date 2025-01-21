#!/usr/bin/python3

import json
import os
import shlex
import subprocess
import sys
import typing

# This script wraps the command-line arguments passed to it to run as an
# unprivileged user in a gVisor sandbox.
# Its behavior can be modified with the following environment variables:
#   RUNSC_DEBUG: If set, print debug messages to stderr, and log all gVisor
#                output to stderr.
#   RUNSC_FLAGS: If set, pass these flags to the `runsc` invocation.
# These environment variables are not passed on to the sandboxed process.


def log(message: str, *values: typing.Any) -> None:
    """Helper function to log messages if RUNSC_DEBUG is set."""
    if os.environ.get("RUNSC_DEBUG"):
        print(message.format(*values), file=sys.stderr)


command = sys.argv[1:]
if len(command) == 0:
    log("Invoked without a command; will execute 'sh'.")
    command = ["sh"]
else:
    log("Invoked with command: {}", " ".join(shlex.quote(s) for s in command))

# Build and write container OCI config.
oci_config: dict[str, typing.Any] = {
    "ociVersion": "1.0.0",
    "process": {
        "user": {
            # Hardcode the UID/GID of the container image to 1000, since we're in
            # control of the image creation, and we don't expect it to change.
            "uid": 1000,
            "gid": 1000,
        },
        "args": command,
        "env": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH=/opt/dangerzone",
            "TERM=xterm",
        ],
        "cwd": "/",
        "capabilities": {
            "bounding": [],
            "effective": [],
            "inheritable": [],
            "permitted": [],
        },
        "rlimits": [
            {"type": "RLIMIT_NOFILE", "hard": 4096, "soft": 4096},
        ],
    },
    "root": {"path": "/", "readonly": True},
    "hostname": "dangerzone",
    "mounts": [
        # Mask almost every system directory of the outer container, by mounting tmpfs
        # on top of them. This is done to avoid leaking any sensitive information,
        # either mounted by Podman/Docker, or when gVisor runs, since we reuse the same
        # rootfs. We basically mask everything except for `/usr`, `/bin`, `/lib`,
        # and `/etc`.
        #
        # Note that we set `--root /home/dangerzone/.containers` for the directory where
        # gVisor will create files at runtime, which means that in principle, we are
        # covered by the masking of `/home/dangerzone` that follows below.
        #
        # Finally, note that the following list has been taken from the dirs in our
        # container image, and double-checked against the top-level dirs listed in the
        # Filesystem Hierarchy Standard (FHS) [1]. It would be nice to have an allowlist
        # approach instead of a denylist, but FHS is such an old standard that we don't
        # expect any new top-level dirs to pop up any time soon.
        #
        # [1] https://en.wikipedia.org/wiki/Filesystem_Hierarchy_Standard
        {
            "destination": "/boot",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/dev",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        {
            "destination": "/home",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/media",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/mnt",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/proc",
            "type": "proc",
            "source": "proc",
        },
        {
            "destination": "/root",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/run",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        {
            "destination": "/sbin",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/srv",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/sys",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev", "ro"],
        },
        {
            "destination": "/tmp",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        {
            "destination": "/var",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        # Also mask some files that are usually mounted by Docker / Podman. These files
        # should not contain any sensitive information, since we use the `--network
        # none` flag, but we want to make sure in any case.
        {
            "destination": "/etc/hostname",
            "type": "bind",
            "source": "/dev/null",
            "options": ["rbind", "ro"],
        },
        {
            "destination": "/etc/hosts",
            "type": "bind",
            "source": "/dev/null",
            "options": ["rbind", "ro"],
        },
        # LibreOffice needs a writable home directory, so just mount a tmpfs
        # over it.
        {
            "destination": "/home/dangerzone",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        # Used for LibreOffice extensions, which are only conditionally
        # installed depending on which file is being converted.
        {
            "destination": "/usr/lib/libreoffice/share/extensions/",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
    ],
    "linux": {
        "namespaces": [
            {"type": "pid"},
            {"type": "network"},
            {"type": "ipc"},
            {"type": "uts"},
            {"type": "mount"},
        ],
    },
}
not_forwarded_env = set(
    (
        "PATH",
        "HOME",
        "SHLVL",
        "HOSTNAME",
        "TERM",
        "PWD",
        "RUNSC_FLAGS",
        "RUNSC_DEBUG",
    )
)
for key_val in oci_config["process"]["env"]:
    not_forwarded_env.add(key_val[: key_val.index("=")])
for key, val in os.environ.items():
    if key in not_forwarded_env:
        continue
    oci_config["process"]["env"].append("%s=%s" % (key, val))
if os.environ.get("RUNSC_DEBUG"):
    log("Command inside gVisor sandbox: {}", command)
    log("OCI config:")
    json.dump(oci_config, sys.stderr, indent=2, sort_keys=True)
    # json.dump doesn't print a trailing newline, so print one here:
    log("")
with open("/config.json", "w") as oci_config_out:
    json.dump(oci_config, oci_config_out, indent=2, sort_keys=True)

# Run gVisor.
runsc_argv = [
    "/usr/bin/runsc",
    "--rootless=true",
    "--network=none",
    "--root=/home/dangerzone/.containers",
    # Disable DirectFS for to make the seccomp filter even stricter,
    # at some performance cost.
    "--directfs=false",
]
if os.environ.get("RUNSC_DEBUG"):
    runsc_argv += ["--debug=true", "--alsologtostderr=true"]
if os.environ.get("RUNSC_FLAGS"):
    runsc_argv += [x for x in shlex.split(os.environ.get("RUNSC_FLAGS", "")) if x]
runsc_argv += ["run", "--bundle=/", "dangerzone"]
log(
    "Running gVisor with command line: {}", " ".join(shlex.quote(s) for s in runsc_argv)
)
runsc_process = subprocess.run(
    runsc_argv,
    check=False,
)
log("gVisor quit with exit code: {}", runsc_process.returncode)

# We're done.
sys.exit(runsc_process.returncode)
