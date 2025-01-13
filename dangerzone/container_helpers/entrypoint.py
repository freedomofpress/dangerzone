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
        {
            "destination": "/proc",
            "type": "proc",
            "source": "proc",
        },
        {
            "destination": "/dev",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
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
