import contextlib
import functools
import json
import logging
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .. import container_utils, util
from ..errors import OtherMachineRunningError
from .command import PodmanCommand
from .errors import CommandError, PodmanError, PodmanNotInstalled

logger = logging.getLogger(__name__)


class PodmanMachineManager:
    """Manages the lifecycle of Dangerzone's Podman machines."""

    def __init__(self) -> None:
        """Initialize the PodmanMachineManager."""
        self.name = container_utils.PODMAN_MACHINE_NAME
        self.prefix = container_utils.PODMAN_MACHINE_PREFIX

    @functools.cached_property
    def podman(self) -> PodmanCommand:
        """Instantiate a PodmanCommand class."""
        return container_utils.init_podman_command()

    def _get_machine_image_path(self) -> Path:
        """Get the path to the machine image."""
        return util.get_resource_path("machine.tar")

    def _get_existing_dangerzone_machines(self) -> List[Dict]:
        """Get a list of existing Dangerzone machines."""
        try:
            machines = self.podman.machine.list()
            return [m for m in machines if m.get("Name", "").startswith(self.prefix)]
        except (CommandError, json.JSONDecodeError):
            return []

    def _remove_stale_machines(self, existing_machines: List[Dict]) -> None:
        """Remove stale Dangerzone machines."""
        for machine in existing_machines:
            name = machine.get("Name")
            if name and name != self.name:
                logger.info(f"Removing stale Podman machine: {name}")
                try:
                    self.remove(name=name)
                except CommandError as e:
                    logger.warning(f"Failed to remove stale machine {name}: {e}")

    def list_other_running_machines(self) -> List[str]:
        """List other running Podman machines, excluding the expected one."""
        other_running_machines = []
        try:
            machines = self.podman.machine.list()
            for machine in machines:
                name = machine.get("Name")
                if name and name != self.name and machine.get("Running"):
                    other_running_machines.append(name)
        except (CommandError, json.JSONDecodeError):
            pass
        return other_running_machines

    def init(
        self,
        cpus: Optional[int] = None,
        memory: Optional[int] = None,
        timezone: str = "Etc/UTC",  # Do not leak local timezone
    ) -> None:
        """Initialize a new Podman machine."""
        existing_machines = self._get_existing_dangerzone_machines()
        self._remove_stale_machines(existing_machines)

        if any(m.get("Name") == self.name for m in existing_machines):
            logger.info(f"Podman machine '{self.name}' already exists.")
            return

        logger.info(f"Initializing Podman machine: {self.name}")
        self.podman.machine.init(
            name=self.name,
            cpus=cpus,
            memory=memory,
            timezone=timezone,
            image=self._get_machine_image_path(),
            capture_output=False,
        )
        logger.info(f"Podman machine '{self.name}' initialized successfully.")

    def start(self, name: Optional[str] = None) -> None:
        """Start a Podman machine."""
        if name is None:
            name = self.name

        if platform.system() == "Darwin":
            other_running_machines = self.list_other_running_machines()
            if other_running_machines:
                raise OtherMachineRunningError(
                    f"Other Podman machines are running: {', '.join(other_running_machines)}"
                )

        logger.info(f"Starting Podman machine: {name}")
        try:
            self.podman.machine.start(name=name, capture_output=False)
            logger.info(f"Podman machine '{name}' started successfully.")
        except CommandError as e:
            for m in self._get_existing_dangerzone_machines():
                if m.get("Name") == self.name and m.get("Running"):
                    logger.info(f"Podman machine '{name}' is already running")
                    return
            raise

    def stop(
        self,
        name: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Stop a Podman machine."""
        if name is None:
            name = self.name
        logger.info(f"Stopping Podman machine: {name}")
        self.podman.machine.stop(name=name, wait=wait)
        if wait:
            logger.info(f"Podman machine '{name}' stopped successfully.")

    def remove(self, name: Optional[str] = None) -> None:
        """Remove a Podman machine."""
        if name is None:
            name = self.name
        logger.info(f"Removing Podman machine: {name}")
        self.podman.machine.remove(name=name)
        logger.info(f"Podman machine '{name}' removed successfully.")

    def reset(self) -> None:
        """Reset all Podman machines."""
        logger.info("Resetting all Podman machines.")
        self.podman.machine.reset()
        logger.info("Podman machines reset successfully.")

    def list(self) -> List[Dict]:
        """List all Dangerzone machines."""
        return self._get_existing_dangerzone_machines()

    def run_raw_podman_command(self, args: List[str]) -> Union[str, subprocess.Popen]:
        """Run a raw Podman command."""
        return self.podman.run(args, stdin=None, capture_output=False)
