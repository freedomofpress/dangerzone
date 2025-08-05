import dataclasses
import logging
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

from .. import errors

logger = logging.getLogger("podman.command.cli_runner")


@dataclasses.dataclass
class GlobalOptions:
    """Global options for Podman commands.

    Attributes:
        cdi_spec_dir (Union[str, Path, list[str], list[Path], None]): The CDI spec directory path (can be a list of paths).
        cgroup_manager: CGroup manager to use.
        config: Location of config file, mainly for Docker compatibility.
        conmon: Path to the conmon binary.
        connection: Connection to use for remote Podman.
        events_backend: Backend to use for storing events.
        hooks_dir: Directory for hooks (can be a list of directories).
        identity: Path to SSH identity file.
        imagestore: Path to the image store.
        log_level: Logging level.
        module: Load a containers.conf module.
        network_cmd_path: Path to slirp4netns command.
        network_config_dir: Path to network config directory.
        remote: When true, access to the Podman service is remote.
        root: Storage root dir in which data, including images, is stored
        runroot: Storage state directory where all state information is stored
        runtime: Name or path of the OCI runtime.
        runtime_flag: Global flags for the container runtime
        ssh: Change SSH mode.
        storage_driver: Storage driver to use.
        storage_opt: Storage options.
        syslog: Output logging information to syslog as well as the console.
        tmpdir: Path to the tmp directory, for libpod runtime content.
        transient_store: Whether to use a transient store.
        url: URL for Podman service.
        volumepath: Volume directory where builtin volume information is stored
    """

    cdi_spec_dir: Union[str, Path, list[str], list[Path], None] = None
    cgroup_manager: Union[str, None] = None
    config: Union[str, Path, None] = None
    conmon: Union[str, Path, None] = None
    connection: Union[str, None] = None
    events_backend: Union[str, None] = None
    hooks_dir: Union[str, Path, list[str], list[Path], None] = None
    identity: Union[str, Path, None] = None
    imagestore: Union[str, None] = None
    log_level: Union[str, None] = None
    module: Union[str, None] = None
    network_cmd_path: Union[str, Path, None] = None
    network_config_dir: Union[str, Path, None] = None
    remote: Union[bool, None] = None
    root: Union[str, Path, None] = None
    runroot: Union[str, Path, None] = None
    runtime: Union[str, Path, None] = None
    runtime_flag: Union[str, list[str], None] = None
    ssh: Union[str, None] = None
    storage_driver: Union[str, None] = None
    storage_opt: Union[str, list[str], None] = None
    syslog: Union[bool, None] = None
    tmpdir: Union[str, Path, None] = None
    transient_store: Union[bool, None] = False
    url: Union[str, None] = None
    volumepath: Union[str, Path, None] = None


def get_subprocess_startupinfo():
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None


class Runner:
    """Runner class to execute Podman commands.

    Attributes:
        podman_path (Path): Path to the Podman executable.
        privileged (bool): Whether to run commands with elevated privileges.
        options (GlobalOptions): Global options for Podman commands.
        env (dict): Environment variables for the subprocess.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        privileged: bool = False,
        options: Optional[GlobalOptions] = None,
        env: Optional[dict] = None,
    ):
        """Initialize the Runner.

        Args:
            path (Path, optional): Path to the Podman executable. Defaults to the system path.
            privileged (bool, optional): Whether to run commands with elevated privileges. Defaults to False.
            options (GlobalOptions, optional): Global options for Podman commands. Defaults to None.
            env (dict, optional): Environment variables for the subprocess. Defaults to None.

        Raises:
            errors.PodmanNotInstalled: If Podman is not installed.
        """
        if path is None:
            path = shutil.which("podman")
            if path is None:
                raise errors.PodmanNotInstalled()
            path = Path(path)

        self.podman_path = path
        if privileged and platform.system() == "Windows":
            raise errors.PodmanError("Cannot run privileged Podman command on Windows")
        self.privileged = privileged
        self.options = options
        self.env = env

    def display(self, cmd):
        """Display a list of command-line options as a single command invocation."""
        parts = [str(part) for part in cmd]
        return shlex.join(parts)

    def format_cli_opts(self, *args, **kwargs) -> list[str]:
        """Format Pythonic arguments into command-line options for the Podman command.

        Args:
            *args: Positional arguments to format.
            **kwargs: Keyword arguments to format.

        Returns:
            list[str]: A list of formatted command-line options.
        """
        cmd = []
        # Positional arguments (*args) are added as is, provided that they are
        # defined.
        for arg in args:
            if arg is not None:
                cmd.append(arg)

        for arg, value in kwargs.items():
            option_name = "--" + arg.replace("_", "-")
            if value is True:
                # Options like cli_flag=True get converted to ["--cli-flag"].
                cmd.append(option_name)
            elif isinstance(value, list):
                # Options like cli_flag=["foo", "bar"] get converted to
                # ["--cli-flag", "foo", "--cli-flag", "bar"].
                for v in value:
                    cmd += [option_name, str(v)]
            elif value is not None and value is not False:
                # Options like cli_flag="foo" get converted to
                # ["--cli-flag", "foo"].
                cmd += [option_name, str(value)]
        return cmd

    def construct(self, *args, **kwargs) -> list[str]:
        """Construct the full command to run.

        Construct the base Podman command, along with the global CLI options.
        Then, format the Pythonic arguments for the Podman command
        (*args/**kwargs) and append them to the final command.

        Args:
            *args: Positional arguments for the command.
            **kwargs: Keyword arguments for the command.

        Returns:
            list[str]: The constructed command as a list of strings.
        """
        cmd = []
        if self.privileged:
            cmd.append("sudo")

        cmd.append(str(self.podman_path))

        if self.options:
            cmd += self.format_cli_opts(**dataclasses.asdict(self.options))

        cmd += self.format_cli_opts(*args, **kwargs)
        return cmd

    def run(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output=True,
        wait=True,
        **skwargs,
    ) -> Union[str, subprocess.Popen, None]:
        """Run the specified Podman command.

        Args:
            cmd (list[str]): The command to run, as a list of strings.
            check (bool, optional): Whether to check for errors. Defaults to True.
            capture_output (bool, optional): Whether to capture output. Defaults to True.
            wait (bool, optional): Whether to wait for the command to complete. Defaults to True.
            **skwargs: Additional keyword arguments for subprocess.

        Returns:
            Optional[str]: The output of the command if captured, otherwise the
                subprocess.Popen instance.

        Raises:
            errors.CommandError: If the command fails.
        """
        cmd = self.construct() + cmd
        return self.run_raw(
            cmd, check=check, capture_output=capture_output, wait=wait, **skwargs
        )

    def run_raw(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        wait=True,
        **skwargs,
    ) -> Union[str, subprocess.Popen, None]:
        """Run the command without additional construction. Mostly for internal use.

        Args:
            cmd (list[str]): The full command to run.
            check (bool, optional): Whether to check for errors. Defaults to True.
            capture_output (bool, optional): Whether to capture output. Defaults to True.
            stdin: Control the process' stdin. Disabled by default, to avoid hanging commands.
            wait (bool, optional): Whether to wait for the command to complete. Defaults to True.
            **skwargs: Additional keyword arguments for subprocess.

        Returns:
            Optional[str]: The output of the command if captured, otherwise the
                subprocess.Popen instance.

        Raises:
            errors.CommandError: If the command fails.
        """
        logger.debug(f"Running: {self.display(cmd)}")
        skwargs.setdefault("startupinfo", get_subprocess_startupinfo())
        if not wait:
            skwargs.setdefault("stdin", stdin)
            return subprocess.Popen(
                cmd,
                env=self.env,
                **skwargs,
            )

        try:
            skwargs.setdefault("check", check)
            skwargs.setdefault("capture_output", capture_output)
            skwargs.setdefault("stdin", stdin)
            ret = subprocess.run(
                cmd,
                env=self.env,
                **skwargs,
            )
        except subprocess.CalledProcessError as e:
            raise errors.CommandError(e) from e
        if capture_output:
            return ret.stdout.decode().rstrip()
