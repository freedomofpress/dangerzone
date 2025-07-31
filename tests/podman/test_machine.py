import json
import platform
from pathlib import Path

import pytest
from pytest_subprocess import FakeProcess

from dangerzone.podman.machine import PodmanMachineManager
from dangerzone.util import get_version


@pytest.fixture
def machine_manager(mocker) -> PodmanMachineManager:
    return PodmanMachineManager()


def test_initialize_machine_no_existing(
    machine_manager: PodmanMachineManager, fp: FakeProcess
) -> None:
    """Test that the initialize_machine method runs the correct commands when no machine exists."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    podman_path = str(machine_manager.podman.runner.podman_path)
    image_path = str(machine_manager._get_machine_image_path())
    fp.register(
        [podman_path, "machine", "list", "--format", "json"],
        stdout=json.dumps([]),
    )
    fp.register([podman_path, "machine", "init", machine_name, "--image", image_path])
    machine_manager.init()


def test_initialize_machine_stale_exists(
    machine_manager: PodmanMachineManager, fp: FakeProcess
) -> None:
    """Test that stale machines are removed during initialization."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    stale_machine_name = "dz-internal-stale"
    podman_path = str(machine_manager.podman.runner.podman_path)
    image_path = str(machine_manager._get_machine_image_path())

    fp.register(
        [podman_path, "machine", "list", "--format", "json"],
        stdout=json.dumps([{"Name": stale_machine_name}]),
    )
    fp.register([podman_path, "machine", "rm", stale_machine_name, "--force"])
    fp.register([podman_path, "machine", "init", machine_name, "--image", image_path])
    machine_manager.init()


def test_start_machine(machine_manager: PodmanMachineManager, fp: FakeProcess) -> None:
    """Test that the start_machine method runs the correct commands."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    podman_path = str(machine_manager.podman.runner.podman_path)
    fp.register([podman_path, "machine", "start", machine_name])
    machine_manager.start()


def test_stop_machine(machine_manager: PodmanMachineManager, fp: FakeProcess) -> None:
    """Test that the stop_machine method runs the correct commands."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    podman_path = str(machine_manager.podman.runner.podman_path)
    fp.register([podman_path, "machine", "stop", machine_name])
    machine_manager.stop()


def test_remove_machine(machine_manager: PodmanMachineManager, fp: FakeProcess) -> None:
    """Test that the remove_machine method runs the correct commands."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    podman_path = str(machine_manager.podman.runner.podman_path)
    fp.register([podman_path, "machine", "rm", machine_name, "--force"])
    machine_manager.remove(force=True)


def test_reset_machines(machine_manager: PodmanMachineManager, fp: FakeProcess) -> None:
    """Test that the reset_machines method runs the correct commands."""
    podman_path = str(machine_manager.podman.runner.podman_path)
    fp.register([podman_path, "machine", "reset", "--force"])
    machine_manager.reset()


def test_list_dangerzone_machines(
    machine_manager: PodmanMachineManager, fp: FakeProcess
) -> None:
    """Test that list_dangerzone_machines filters correctly."""
    podman_path = str(machine_manager.podman.runner.podman_path)
    fp.register(
        [podman_path, "machine", "list", "--format", "json"],
        stdout=json.dumps(
            [{"Name": "dz-internal-1"}, {"Name": "other"}, {"Name": "dz-internal-2"}]
        ),
    )
    machines = machine_manager.list()
    assert len(machines) == 2
    assert machines[0]["Name"] == "dz-internal-1"
    assert machines[1]["Name"] == "dz-internal-2"


def test_run_raw_podman_command(
    machine_manager: PodmanMachineManager, fp: FakeProcess
) -> None:
    """Test that run_raw_podman_command executes the command."""
    podman_path = str(machine_manager.podman.runner.podman_path)
    raw_command = ["info"]
    fp.register([podman_path] + raw_command)
    machine_manager.run_raw_podman_command(raw_command)
    assert fp.call_count([podman_path] + raw_command) == 1
