import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from ..util import get_subprocess_startupinfo

logger = logging.getLogger(__name__)

ENV_CONTAINERS_CONF = "CONTAINERS_CONF"


class Runner:
    def __init__(self, path: Path = None, containers_conf: Path = None):
        self.podman_path = path or Path(shutil.which("podman"))
        self.containers_conf = containers_conf

    def construct(self, *args, **kwargs) -> list[str]:
        cmd = []
        for arg, value in kwargs.items():
            option_name = "--" + arg.replace("_", "-")
            if value is True:
                cmd.append(option_name)
            elif value:
                cmd += [option_name, value]
        for arg in args:
            cmd.append(arg)
        return cmd

    def display(self, cmd):
        parts = [str(part) for part in cmd]
        return shlex.join(parts)

    def run_raw(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output=True,
        **skwargs,
    ):
        cmd = [self.podman_path] + cmd
        env = os.environ.copy()
        if self.containers_conf:
            env["ENV_CONTAINERS_CONF"] = containers_conf

        logger.warn(f"Running: {self.display(cmd)}")
        ret = subprocess.run(
            cmd,
            env=env,
            check=check,
            capture_output=True,
            startupinfo=get_subprocess_startupinfo(),
            **skwargs,
        )
        return ret.stdout.decode().rstrip()
