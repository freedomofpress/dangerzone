import json
from pathlib import Path

from ..util import get_binary_path
from . import cli_runner

MACHINE_OS_IMAGE = "quay.io/podman/machine-os"
MACHINE_OS_WSL_IMAGE = "quay.io/podman/machine-os-wsl"


def download_image(os):
    vers = version.client_version()
    crane = get_binary_path("crane")

    cmd = [crane, "version"]
    return command.raw_run(cmd)


class MachineManager:
    def __init__(self, runner: cli_runner.Runner):
        self.runner = runner

    def list(self, all_providers=False) -> dict:
        cmd = ["machine", "list"]
        cmd += self.runner.construct(format="json", all_providers=all_providers)
        return json.loads(self.runner.run_raw(cmd))

    def init(
        self,
        name: str = None,
        cpus: int = None,
        disk_size: int = None,
        ignition_path: Path = None,
        image: str | Path = None,
        memory: int = None,
        now: bool = False,
        playbook: str = None,
        rootful: bool = False,
        timezone: str = None,
        usb: str = None,
        vendor: str = None,
        user_mode_networking: bool = False,
        username: str = None,
        volume: str = None,
    ) -> None:
        cmd = ["machine", "init"]
        cmd += self.runner.construct(
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
        if name:
            cmd.append(name)
        self.runner.run_raw(cmd)
