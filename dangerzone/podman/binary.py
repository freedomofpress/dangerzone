from pathlib import Path

from . import cli_runner, machine_manager


class PodmanBinary:
    def __init__(self, path: Path = None, containers_conf: Path = None):
        self.runner = cli_runner.Runner(path=path, containers_conf=containers_conf)
        self.machine = machine_manager.MachineManager(self.runner)
