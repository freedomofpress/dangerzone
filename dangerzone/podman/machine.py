import contextlib
import json
import logging
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from .. import util
from .command import PodmanCommand
from .errors import CommandError, PodmanError, PodmanNotInstalled

logger = logging.getLogger(__name__)


class PodmanMachineManager:
    """Manages the lifecycle of Dangerzone's Podman machines."""

    def __init__(self) -> None:
        """Initialize the PodmanMachineManager."""
        self.version = util.get_version()
        self.machine_prefix = f"dz-internal-{self.version}"
        self._podman_path: Optional[Path] = None
        self._podman_command: Optional[PodmanCommand] = None
        self._containers_conf_path: Optional[Path] = None

    @property
    def podman_path(self) -> Path:
        """Get the path to the Podman binary."""
        if self._podman_path is None:
            podman_bin = "podman"
            if platform.system() == "Windows":
                podman_bin += ".exe"
            self._podman_path = (
                util.get_resource_path("vendor") / "podman" / podman_bin)
        return self._podman_path

    @property
    def containers_conf_path(self) -> Path:
        """Create a temporary containers.conf file and return its path."""
        if self._containers_conf_path is None:
            helper_binaries_dir = str(self.podman_path.parent)
            helper_binaries_dir = helper_binaries_dir.replace("\\", "\\\\")
            content = f"""
[containers]
helper_binaries_dir=["{helper_binaries_dir}"]
"""
            fd, path = tempfile.mkstemp(prefix="dangerzone_containers_", suffix=".conf")
            with open(fd, "w") as f:
                f.write(content)
            self._containers_conf_path = Path(path)
        return self._containers_conf_path

    def _get_machine_image_path(self) -> Path:
        """Get the path to the machine image."""
        return util.get_resource_path("machine.tar")

    def _get_podman_command(self) -> PodmanCommand:
        """Get a PodmanCommand instance."""
        if self._podman_command is None:
            env = os.environ.copy()
            env["CONTAINERS_CONF"] = str(self.containers_conf_path)

            self._podman_command = PodmanCommand(path=self.podman_path, env=env)
        return self._podman_command

    def _install_wsl2(self) -> None:
        """Install WSL2 on Windows."""
        logger.info("Installing WSL2...")
        try:
            subprocess.run(["wsl", "--update"], check=True, capture_output=True)
            subprocess.run(
                ["wsl", "--install", "--no-distribution"],
                check=True,
                capture_output=True,
            )
            logger.info("WSL2 installed successfully.")
        except subprocess.CalledProcessError as e:
            raise PodmanError(f"Failed to install WSL2: {e.stderr.decode()}")

    def _get_existing_dangerzone_machines(self) -> List[Dict]:
        """Get a list of existing Dangerzone machines."""
        cmd = self._get_podman_command()
        try:
            machines = cmd.machine.list()
            return [m for m in machines if m.get("Name", "").startswith("dz-internal-")]
        except (CommandError, json.JSONDecodeError):
            return []

    def _remove_stale_machines(self, existing_machines=List[Dict]) -> None:
        """Remove stale Dangerzone machines."""
        for machine in existing_machines:
            name = machine.get("Name")
            if name and name != self.machine_prefix:
                logger.info(f"Removing stale Podman machine: {name}")
                try:
                    self.remove_machine(name=name, force=True)
                except PodmanError as e:
                    logger.warning(f"Failed to remove stale machine {name}: {e}")

    def initialize_machine(
        self, cpus: int = None, memory: int = None, timezone: str = None
    ) -> None:
        """Initialize a new Podman machine."""
        if platform.system() == "Windows":
            self._install_wsl2()
        existing_machines = self._get_existing_dangerzone_machines()
        self._remove_stale_machines(existing_machines)

        cmd = self._get_podman_command()
        if any(m.get("Name") == self.machine_prefix for m in existing_machines):
            logger.info(f"Podman machine '{self.machine_prefix}' already exists.")
            return

        logger.info(f"Initializing Podman machine: {self.machine_prefix}")
        try:
            cmd.machine.init(
                name=self.machine_prefix,
                cpus=cpus,
                memory=memory,
                timezone=timezone,
                image=self._get_machine_image_path(),
            )
            logger.info(
                f"Podman machine '{self.machine_prefix}' initialized successfully."
            )
        except CommandError as e:
            raise PodmanError(f"Failed to initialize Podman machine: {e}")

    def start_machine(self, name: str = None) -> None:
        """Start a Podman machine."""
        if name is None:
            name = self.machine_prefix
        logger.info(f"Starting Podman machine: {name}")
        try:
            self._get_podman_command().machine.start(name=name)
            logger.info(f"Podman machine '{name}' started successfully.")
        except CommandError as e:
            raise PodmanError(f"Failed to start Podman machine: {e}")

    def stop_machine(self, name: str = None) -> None:
        """Stop a Podman machine."""
        if name is None:
            name = self.machine_prefix
        logger.info(f"Stopping Podman machine: {name}")
        try:
            self._get_podman_command().machine.stop(name=name)
            logger.info(f"Podman machine '{name}' stopped successfully.")
        except CommandError as e:
            logger.warning(f"Failed to stop Podman machine: {e}")

    def remove_machine(self, name: str = None, force: bool = False) -> None:
        """Remove a Podman machine."""
        if name is None:
            name = self.machine_prefix
        logger.info(f"Removing Podman machine: {name}")
        try:
            self._get_podman_command().machine.remove(name=name, force=force)
            logger.info(f"Podman machine '{name}' removed successfully.")
        except CommandError as e:
            logger.warning(f"Failed to remove Podman machine: {e}")

    def reset_machines(self) -> None:
        """Reset all Podman machines."""
        logger.info("Resetting all Podman machines.")
        try:
            self._get_podman_command().machine.reset()
            logger.info("Podman machines reset successfully.")
        except CommandError as e:
            logger.warning(f"Failed to reset Podman machines: {e}")

    def list_dangerzone_machines(self) -> List[Dict]:
        """List all Dangerzone machines."""
        return self._get_existing_dangerzone_machines()

    def run_raw_podman_command(self, args: List[str]) -> Union[str, subprocess.Popen]:
        """Run a raw Podman command."""
        return self._get_podman_command().run(args)
