import builtins
import json
import subprocess
from pathlib import Path
from typing import Union

from . import cli_runner


class MachineManager:
    """Manager for handling Podman machine operations.

    Attributes:
        runner (cli_runner.Runner): The runner instance to execute commands.
    """

    def __init__(self, runner: cli_runner.Runner):
        """Initialize the MachineManager.

        Args:
            runner (cli_runner.Runner): The runner instance to execute commands.
        """
        self.runner = runner

    def list(self, all_providers: bool = False, **skwargs) -> dict:
        """List all machines.

        Args:
            all_providers (bool, optional): Whether to include all providers. Defaults to False.
            **skwargs: Additional keyword arguments for subprocess.

        Returns:
            dict: A dictionary containing the list of machines in JSON format.
        """
        cmd = self.runner.construct(
            "machine", "list", format="json", all_providers=all_providers, **skwargs
        )
        return json.loads(self.runner.run_raw(cmd))

    def init(
        self,
        name: str = None,
        cpus: int = None,
        disk_size: int = None,
        ignition_path: Path = None,
        image: Union[str, Path] = None,
        memory: int = None,
        now: bool = False,
        playbook: str = None,
        rootful: bool = False,
        timezone: str = None,
        usb: str = None,
        user_mode_networking: bool = False,
        username: str = None,
        volume: Union[str, builtins.list[str]] = None,
        **skwargs,
    ) -> Union[str, subprocess.Popen]:
        """Initialize a new machine.

        Args:
            name (str, optional): Name of the machine.
            cpus (int, optional): Number of CPUs to allocate.
            disk_size (int, optional): Size of the disk in bytes.
            ignition_path (Path, optional): Path to the ignition file.
            image (Union[str, Path], optional): Image to use for the machine.
            memory (int, optional): Amount of memory in bytes.
            now (bool, optional): Whether to start the machine immediately. Defaults to False.
            playbook (str, optional): Path to an Ansible playbook file.
            rootful (bool, optional): Whether to create a rootful machine. Defaults to False.
            timezone (str, optional): Timezone for the machine.
            usb (str, optional): USB device to attach.
            user_mode_networking (bool, optional): Whether to use user mode networking. Defaults to False.
            username (str, optional): Username for the machine.
            volume (str | list[str], optional): Volume to attach to the machine.
            **skwargs: Additional keyword arguments for subprocess.

        Returns:
            Optional[str]: The output of the command if captured, otherwise the
                subprocess.Popen instance.
        """
        cmd = self.runner.construct(
            "machine",
            "init",
            name,
            cpus=cpus,
            disk_size=disk_size,
            ignition_path=ignition_path,
            image=image,
            memory=memory,
            now=now,
            playbook=playbook,
            rootful=rootful,
            timezone=timezone,
            usb=usb,
            vendor=vendor,
            user_mode_networking=user_mode_networking,
            username=username,
            volume=volume,
        )
        return self.runner.run_raw(cmd, **skwargs)

    def start(self, name: str = None, **skwargs) -> None:
        """Start a machine.

        Args:
            name (str, optional): Name of the machine to start.
        """
        cmd = self.runner.construct("machine", "start", name)
        self.runner.run_raw(cmd, **skwargs)

    def stop(self, name: str = None, **skwargs) -> None:
        """Stop a machine.

        Args:
            name (str, optional): Name of the machine to stop.
        """
        cmd = self.runner.construct("machine", "stop", name)
        self.runner.run_raw(cmd, **skwargs)

    def remove(
        self,
        name: str = None,
        force: bool = False,
        save_image: bool = False,
        save_ignition: bool = False,
        **skwargs,
    ) -> None:
        """Remove a machine.

        Args:
            name (str, optional): Name of the machine to remove.
            force (bool, optional): Whether to stop the machine. Defaults to False.
            save_image (bool, optional): Whether to save the machine's image. Defaults to False.
            save_ignition (bool, optional): Whether to save the ignition file. Defaults to False.
        """
        cmd = self.runner.construct(
            "machine",
            "rm",
            name,
            force=force,
            save_image=save_image,
            save_ignition=save_ignition,
            **skwargs,
        )
        self.runner.run_raw(cmd, **skwargs)

    def reset(self, **skwargs) -> None:
        """Reset Podman machines and environment."""
        cmd = self.runner.construct("machine", "reset", force=True)
        self.runner.run_raw(cmd, **skwargs)
