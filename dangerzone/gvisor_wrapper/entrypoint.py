#!/usr/bin/python3

import argparse
import grp
import json
import os
import pwd
import random
import shlex
import string
import subprocess
import sys
import time
import typing

# This script wraps the command-line arugments passed to it to run as an
# unprivileged user in a gVisor sandbox.
# It is meant to work in both Docker and Podman, which differ in how this
# script is invokved.
# With Docker, the Docker daemon runs as root on the machine, which is
# likely a different user than the one running the Dangerzone application.
# With Podman, which we run in rootless mode, there is only one non-root user
# that is running Podman. In this case, we are UID 0 in the Podman-created
# user namespace, but this user maps to the user running the Dangerzone
# application.
# The script first tries to establish a "common denominator" setup between
# these two situations by checking the owner of the /safezone volume, which
# is mounted by Dangerzone and is owned by the user running this application.
# If this script is not running as this user (i.e. Docker in root mode), it
# re-executes itself as the user owning /safezone. This brings it to the same
# situation as Podman running in rootless mode: there is only one user mapped
# into this user namespace as UID 0, and that user is the person running the
# Dangerzone application on their machine. They do not have root in the
# initial user namespace. No other users are mapped in the user namespace
# we're in.
# However, we now have a second problem: we also want the application running
# within the sandbox to be running as a non-root user with minimal privileges.
# We cannot create a new user here, because such a user would be unmapped in
# the initial user namespace and any attempt to make it into a child user
# namespace (which starting a gVisor sandbox requires) would fail.
# Therefore, the only place where this new user can exist is within the
# gVisor sandbox.
# But now we have a new problem: This user will not have write access to the
# /safezone directory, and any file it does create would be mapped to a
# meaningless user on the host.
# So this script uses a two-volume approach.
# The /safezone directory on the host is mapped to the /host-safezone
# directory in the gVisor sandbox, while a new tmpfs volume is created
# as the sandbox's /safezone directory.
# Then, inside the sandbox right on startup, all files are moved from
# /host-safezone to /safezone and chown'd to the sandbox-only "dangerzone"
# user. Then, when the unprivileged command finishes running, all files
# in the sandbox's /safezone are chown'd back to the sandbox's root user
# (which corresponds to our root user, which in turn corresponds to the
# real user on the host running Dangerzone), and moved back to /host-safezone
# (which makes them show up in the /safezone volume of this container, which
# in turn means they are finally visible on the host).
# This approach is mostly transparent from the perspective of whoever is
# running this container, with the caveats that:
#   - All documents in /safezone must fit in RAM, since they live in tmpfs.
#   - The resulting documents are only visible to the host after the
#     unprivileged command finishes running (as opposed to being available
#     as conversion progresses).
# One alternative to this approach would be to only have the root user exist
# in the sandbox, and to use it directly. It would be possible to drop all
# capabilities from the OCI config below, but it does mean running as UID 0
# within the sandbox.

# Define flags.
parser = argparse.ArgumentParser(
    prog="gvisor_wrapper",
    description="Run a command in a nested gVisor sandbox",
    prefix_chars="-",
    fromfile_prefix_chars=None,
)
flags_with_values = []
parser.add_argument(
    "--pre_gvisor", action="store_true", help="Run command without gVisor wrapping"
)
parser.add_argument(
    "--pre_new_userns", action="store_true", help="Run command before changing userns"
)
parser.add_argument(
    "--pre_sandboxed_entrypoint",
    action="store_true",
    help="Run command in gVisor but without sandboxed_entrypoint.sh",
)
parser.add_argument(
    "--gvisor_debug", action="store_true", help="Enable gVisor debug logging"
)
parser.add_argument(
    "--gvisor_strace", action="store_true", help="Enable system call tracing in gVisor"
)
flags_with_values.append(
    parser.add_argument(
        "--gvisor_flag",
        action="append",
        help="Add gVisor flag, may be specified multiple times",
    )
)
parser.add_argument(
    "command",
    nargs=argparse.PARSER,
    help="Command to run in the sandbox (or outside if --pre_gvisor is specified)",
)

if len(sys.argv) <= 1:  # No arguments: bail.
    print("No command line specified.", file=sys.stderr)
    parser.print_help()
    sys.exit(2)

# We can't pass `sys.argv` directly to `parser` here because this may end up
# processing flags from the wrapped command line that happen to match flags
# that are defined in `parser`. For example, if the user were to somehow
# make a file named `--pre_gvisor`, that would be pretty bad.
# So we scan for the first argument that does not look like it is intended
# for this entrypoint script, and we only pass this subset to `parser`.
parser_args = None
wrapped_command = None
next_arg_is_value_of_previous_flag = False
for i, arg in enumerate(sys.argv):
    if i == 0:
        continue  # Skip argv[0]
    if next_arg_is_value_of_previous_flag:
        next_arg_is_value_of_previous_flag = False
        continue
    if arg == "--":
        parser_args = sys.argv[1:i]
        wrapped_command = sys.argv[i + 1 :]
        break
    if not arg.startswith(parser.prefix_chars):
        parser_args = sys.argv[1:i]
        wrapped_command = sys.argv[i:]
        break
    if "=" not in arg:
        arg_name = arg.lstrip(parser.prefix_chars)
        if any(arg_name == flag.dest for flag in flags_with_values):
            next_arg_is_value_of_previous_flag = True
if parser_args is None or wrapped_command is None:  # No command specified.
    parser_args = sys.argv[1:]
    wrapped_command = []
if len(wrapped_command) == 0:
    wrapped_command = ["sh"]
parser_args.append("command")  # To satisfy the parser's `command` argument.
args = parser.parse_args(parser_args)

if args.pre_new_userns:
    if args.gvisor_debug:
        print(
            "Executing command before userns switch:",
            " ".join(shlex.quote(s) for s in wrapped_command),
            file=sys.stderr,
        )
    try:
        os.execvp(wrapped_command[0], wrapped_command)
    except Exception as e:
        raise e.__class__("Process %s failed: %s" % (wrapped_command, e))
    else:
        assert False, "This code should never be reachable"

# Monkeypatch `os` module for things added in Python 3.12.
# This can go away once the python3 alpine package is updated to 3.12.
if "unshare" not in os.__dict__:
    import ctypes

    libc = ctypes.CDLL(None)
    libc.unshare.argtypes = [ctypes.c_int]
    get_errno_loc = libc.__errno_location
    get_errno_loc.restype.restype = ctypes.POINTER(ctypes.c_int)  # type: ignore[union-attr]

    def unshare_monkeypatch(flags: int) -> None:
        rc = libc.unshare(flags)
        if rc == -1:
            raise Exception(os.strerror(get_errno_loc()[0]))

    os.unshare = unshare_monkeypatch  # type: ignore[attr-defined]
if "CLONE_NEWUSER" not in os.__dict__:
    os.CLONE_NEWUSER = 268435456  # type: ignore[attr-defined]

# Check that we are running as the user that owns /safezone.
# If not, re-exec.
my_uid = os.getuid()
my_gid = os.getgid()
safezone_st = os.lstat("/safezone")

if my_uid == 0 and (safezone_st.st_uid != my_uid or safezone_st.st_gid != my_gid):
    # Need to switch into the user who owns the /safezone directory.
    # This helps preserve the correct user permissions on Docker.
    # The user and group for this UID/GID pair need to exist in the
    # container too before we can use them; if they don't exist,
    # create them.
    # We use random group/user names in order to minimize risk of conflict
    # with existing users in the container.
    try:
        group_name = grp.getgrgid(safezone_st.st_gid).gr_name
    except KeyError:
        add_group_argv = (
            "/usr/sbin/addgroup",
            "-g",
            str(safezone_st.st_gid),
            "danger"
            + "".join(random.choices(string.ascii_lowercase + string.digits, k=24)),
        )
        if args.gvisor_debug:
            print(
                "Creating new group:",
                " ".join(shlex.quote(s) for s in add_group_argv),
                file=sys.stderr,
            )
        subprocess.run(add_group_argv, check=True)
        group_name = grp.getgrgid(safezone_st.st_gid).gr_name
    try:
        user_name = pwd.getpwuid(safezone_st.st_uid).pw_name
    except KeyError:
        add_user_argv = (
            "/usr/sbin/adduser",
            "-u",
            str(safezone_st.st_uid),
            "-s",
            "/bin/true",
            "-G",
            group_name,
            "-D",
            "-H",
            "danger"
            + "".join(random.choices(string.ascii_lowercase + string.digits, k=24)),
        )
        if args.gvisor_debug:
            print(
                "Creating new user:",
                " ".join(shlex.quote(s) for s in add_user_argv),
                file=sys.stderr,
            )
        subprocess.run(add_user_argv, check=True)
        user_name = pwd.getpwuid(safezone_st.st_uid).pw_name
    user_and_group = "%s:%s" % (user_name, group_name)
    # Align permissions of rootfs and runsc state directory to the user we will
    # run it as:
    chown_argv = (
        "/bin/chown",
        "-R",
        user_and_group,
        "/var/run/runsc",
        "/wrapped-safezone",
        "/dangerzone-image",
    )
    if args.gvisor_debug:
        print(
            "Setting permissions to sandbox user:",
            " ".join(shlex.quote(s) for s in add_group_argv),
            file=sys.stderr,
        )
    subprocess.run(chown_argv, check=True)

    # Switch to target user.
    su_exec_argv = ("su-exec", user_and_group) + tuple(sys.argv)
    if args.gvisor_debug:
        print(
            "Re-executing as",
            user_and_group,
            "->",
            " ".join(shlex.quote(s) for s in su_exec_argv),
            file=sys.stderr,
        )
    try:
        os.execv("/sbin/su-exec", su_exec_argv)
    except Exception as e:
        raise e.__class__("su-exec %s failed: %s" % (sys.argv, e))
    else:
        assert False, "This code should never be reachable"

if my_uid != 0:
    # If we are not UID 0, create a user namespace where we are mapped to it.
    if args.gvisor_debug:
        print(
            "Current UID/GID is %d:%d; creating new user namespace..."
            % (my_uid, my_gid),
            file=sys.stderr,
        )
    os.unshare(os.CLONE_NEWUSER)  # type: ignore[attr-defined]
    with os.fdopen(
        os.open("/proc/self/setgroups", flags=os.O_WRONLY), "wt"
    ) as setgroups_fd:
        setgroups_fd.write("deny")
    with os.fdopen(
        os.open("/proc/self/uid_map", flags=os.O_WRONLY), "wt"
    ) as uid_map_fd:
        uid_map_fd.write("0 %d 1" % (my_uid,))
    with os.fdopen(
        os.open("/proc/self/gid_map", flags=os.O_WRONLY), "wt"
    ) as gid_map_fd:
        gid_map_fd.write("0 %d 1" % (my_gid,))
    # Re-exec.
    if args.gvisor_debug:
        print("Re-execing:", " ".join(shlex.quote(s) for s in sys.argv))
    try:
        os.execvp(sys.argv[0], sys.argv)
    except Exception as e:
        raise e.__class__("Re-execing %s failed: %s" % (sys.argv, e))
    else:
        assert False, "This code should never be reachable"

# By this point, we are running as the same user that owns /safezone and
# that user is mapped to UID 0 in a dedicated user namespace.

# Build and write container OCI config.
oci_command = wrapped_command
if not args.pre_sandboxed_entrypoint:
    oci_command = ["/sandboxed_entrypoint.sh"] + oci_command

oci_config: dict[str, typing.Any] = {
    "ociVersion": "1.0.0",
    "process": {
        "user": {"uid": 0, "gid": 0},
        "args": oci_command,
        "env": [
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH=/opt/dangerzone",
            "TERM=xterm",
        ],
        "cwd": "/",
        "capabilities": {
            # See the long comment above as to why this is needed.
            # CAP_CHOWN is needed to chown the safezone files back and forth.
            # CAP_SETUID and CAP_SETGID are required to switch to the
            # unprivileged user.
            "bounding": ["CAP_CHOWN", "CAP_SETUID", "CAP_SETGID"],
            "effective": ["CAP_CHOWN", "CAP_SETUID", "CAP_SETGID"],
            "inheritable": ["CAP_CHOWN", "CAP_SETUID", "CAP_SETGID"],
            "permitted": ["CAP_CHOWN", "CAP_SETUID", "CAP_SETGID"],
        },
        "rlimits": [
            {"type": "RLIMIT_NOFILE", "hard": 4096, "soft": 4096},
        ],
    },
    "root": {"path": "rootfs", "readonly": True},
    "hostname": "dangerzone",
    "mounts": [
        {
            "destination": "/proc",
            "type": "proc",
            "source": "proc",
        },
        # /safezone is a tmpfs which will be owned by the unprivileged user
        # which lives only in the sandbox. See comment above.
        {
            "destination": "/safezone",
            "type": "tmpfs",
            "source": "tmpfs",
            "options": ["nosuid", "noexec", "nodev"],
        },
        # /host-safezone is where the host's /safezone is actually mounted.
        {
            "destination": "/host-safezone",
            "type": "none",
            "source": "/safezone",
            "options": ["bind", "nosuid", "noexec", "nodev", "rw"],
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
not_forwarded_env = set(("PATH", "HOME", "SHLVL", "HOSTNAME", "TERM", "PWD"))
for key_val in oci_config["process"]["env"]:
    not_forwarded_env.add(key_val[: key_val.index("=")])
for key, val in os.environ.items():
    if key in not_forwarded_env:
        continue
    oci_config["process"]["env"].append("%s=%s" % (key, val))
if args.gvisor_debug:
    print("Command inside gVisor sandbox:", oci_command, file=sys.stderr)
    print("OCI config:", file=sys.stderr)
    json.dump(oci_config, sys.stderr, indent=2, sort_keys=True)
    # json.dump doesn't print a trailing newline, so print one here:
    print("", file=sys.stderr)
with open("/dangerzone-image/config.json", "w") as oci_config_out:
    json.dump(oci_config, oci_config_out, indent=2, sort_keys=True)

# Run gVisor.
runsc_binary = "/usr/bin/runsc"
runsc_argv = [os.path.basename(runsc_binary), "--rootless=true", "--network=none"]
if args.gvisor_debug:
    runsc_argv += ["--debug=true", "--alsologtostderr=true"]
if args.gvisor_strace:
    runsc_argv += ["--strace=true"]
if args.gvisor_flag is not None:
    for gvisor_flag in args.gvisor_flag:
        if gvisor_flag:
            runsc_argv += [gvisor_flag]
runsc_argv += ["run", "--bundle=/dangerzone-image", "dangerzone"]

# Check for `--pre_gvisor` which can be used to run commands without wrapping.
if args.pre_gvisor:
    print(
        "Would be running the following command if --pre_gvisor had not been specified:",
        " ".join(shlex.quote(s) for s in runsc_argv),
        file=sys.stderr,
    )
    print(
        "Executing this command instead:",
        " ".join(shlex.quote(s) for s in wrapped_command),
        file=sys.stderr,
    )
    try:
        os.execvp(wrapped_command[0], wrapped_command)
    except Exception as e:
        raise e.__class__("Process %s failed: %s" % (wrapped_command, e))
    else:
        assert False, "This code should never be reachable"

if args.gvisor_debug:
    print(
        "Running",
        runsc_binary,
        "with command line:",
        " ".join(shlex.quote(s) for s in runsc_argv),
        file=sys.stderr,
    )
runsc_process = subprocess.run(
    runsc_argv,
    executable=runsc_binary,
    check=False,
)
if args.gvisor_debug:
    print("gVisor quit with exit code:", runsc_process.returncode, file=sys.stderr)

# We're done.
sys.exit(runsc_process.returncode)
