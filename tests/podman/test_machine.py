import json
import platform
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from pytest_subprocess import FakeProcess

from dangerzone import container_utils
from dangerzone import errors as dz_errors
from dangerzone.podman import errors
from dangerzone.podman.machine import PodmanMachineManager
from dangerzone.util import get_version


@pytest.fixture
def machine_manager(mocker: MockerFixture) -> PodmanMachineManager:
    return PodmanMachineManager()


@pytest.fixture
def podman_register(fp: FakeProcess, machine_manager: PodmanMachineManager) -> Callable:
    version = get_version()
    machine_name = f"dz-internal-{version}"
    podman_path = str(machine_manager.podman.runner.podman_path)

    base_cmd = [podman_path]
    if platform.system() != "Linux":
        base_cmd += ["--connection", machine_name]

    def fp_register(cmd: list[str], **kwargs):  # type: ignore [no-untyped-def]
        return fp.register(base_cmd + cmd, **kwargs)

    return fp_register


def test_initialize_machine_no_existing(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that the initialize_machine method runs the correct commands when no machine exists."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    image_path = str(machine_manager._get_machine_image_path())
    rec_list = podman_register(
        ["machine", "list", "--format", "json"], stdout=json.dumps([])
    )
    rec_init = podman_register(
        [
            "machine",
            "init",
            machine_name,
            "--image",
            image_path,
            "--timezone",
            "Etc/UTC",
        ]
    )
    machine_manager.init()
    assert rec_list.call_count() == 1
    assert rec_init.call_count() == 1


def test_initialize_machine_stale_exists(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that stale machines are removed during initialization."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    stale_machine_name = "dz-internal-stale"
    image_path = str(machine_manager._get_machine_image_path())

    rec_list = podman_register(
        ["machine", "list", "--format", "json"],
        stdout=json.dumps([{"Name": stale_machine_name}]),
    )
    rec_rm = podman_register(["machine", "rm", stale_machine_name, "--force"])
    rec_init = podman_register(
        [
            "machine",
            "init",
            machine_name,
            "--image",
            image_path,
            "--timezone",
            "Etc/UTC",
        ]
    )
    machine_manager.init()
    assert rec_list.call_count() == 1
    assert rec_rm.call_count() == 1
    assert rec_init.call_count() == 1


def test_start_machine_success(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that the machine starts normally if nothing else is running"""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    if platform.system() == "Darwin":
        rec_list_other = podman_register(
            ["machine", "list", "--format", "json"], stdout=json.dumps([])
        )
    rec_start = podman_register(["machine", "start", machine_name])
    machine_manager.start()
    if platform.system() == "Darwin":
        assert rec_list_other.call_count() == 1
    assert rec_start.call_count() == 1


def test_start_machine_already_running(
    machine_manager: PodmanMachineManager,
    podman_register: Callable,
    mocker: MockerFixture,
) -> None:
    """Test that start() does not fail if machine is already running."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    rec_start = podman_register(["machine", "start", machine_name], returncode=1)
    if platform.system() == "Darwin":
        rec_list_other = podman_register(
            ["machine", "list", "--format", "json"],
            stdout=json.dumps([{"Name": machine_name, "Running": True}]),
        )
    rec_list = podman_register(
        ["machine", "list", "--format", "json"],
        stdout=json.dumps([{"Name": machine_name, "Running": True}]),
    )
    machine_manager.start()
    if platform.system() == "Darwin":
        assert rec_list_other.call_count() == 1
    assert rec_start.call_count() == 1
    assert rec_list.call_count() == 1


@pytest.mark.skipif(platform.system() != "Darwin", reason="MacOS-specific")
def test_start_machine_already_running_other_fail(
    machine_manager: PodmanMachineManager,
    podman_register: Callable,
) -> None:
    """Test that start() fails if another machine is already running on macOS."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    if platform.system() == "Darwin":
        rec_list_other = podman_register(
            ["machine", "list", "--format", "json"],
            stdout=json.dumps([{"Name": "other_machine", "Running": True}]),
        )
    rec_start = podman_register(["machine", "start", machine_name])
    with pytest.raises(dz_errors.OtherMachineRunningError):
        machine_manager.start()
    if platform.system() == "Darwin":
        assert rec_list_other.call_count() == 1
    assert rec_start.call_count() == 0


def test_start_machine_stopped_other_success(
    machine_manager: PodmanMachineManager,
    podman_register: Callable,
) -> None:
    """Test that start() works if another stopped machine exists."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    if platform.system() == "Darwin":
        rec_list_other = podman_register(
            ["machine", "list", "--format", "json"],
            stdout=json.dumps([{"Name": "other_machine", "Running": False}]),
        )
    rec_start = podman_register(["machine", "start", machine_name])
    machine_manager.start()
    if platform.system() == "Darwin":
        assert rec_list_other.call_count() == 1
    assert rec_start.call_count() == 1


def test_start_machine_fail(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that start() fails if `podman machine start` fails and the machine is not
    running."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    rec_start = podman_register(["machine", "start", machine_name], returncode=1)
    if platform.system() == "Darwin":
        rec_list_other = podman_register(
            ["machine", "list", "--format", "json"], stdout=json.dumps([])
        )
    rec_list = podman_register(
        ["machine", "list", "--format", "json"],
        stdout=json.dumps([{"Name": machine_name, "Running": False}]),
    )
    with pytest.raises(errors.CommandError):
        machine_manager.start()
    if platform.system() == "Darwin":
        assert rec_list_other.call_count() == 1
    assert rec_start.call_count() == 1
    assert rec_list.call_count() == 1


def test_stop_machine(
    machine_manager: PodmanMachineManager,
    podman_register: Callable,
    machine_stop: MagicMock,
    mocker: MockerFixture,
) -> None:
    """Test that the stop_machine method runs the correct commands."""
    # Undo the global mock for this specific test, in order to trigger the underlying
    # subprocess command.
    mocker.stop(machine_stop)
    version = get_version()
    machine_name = f"dz-internal-{version}"
    rec_stop = podman_register(["machine", "stop", machine_name])
    machine_manager.stop()
    assert rec_stop.call_count() == 1


def test_remove_machine(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that the remove_machine method runs the correct commands."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    rec_rm = podman_register(["machine", "rm", machine_name, "--force"])
    machine_manager.remove()
    assert rec_rm.call_count() == 1


def test_reset_machines(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that the reset_machines method runs the correct commands."""
    rec_reset = podman_register(["machine", "reset", "--force"])
    machine_manager.reset()
    assert rec_reset.call_count() == 1


def test_list_dangerzone_machines(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that list_dangerzone_machines filters correctly."""
    rec_list = podman_register(
        ["machine", "list", "--format", "json"],
        stdout=json.dumps(
            [{"Name": "dz-internal-1"}, {"Name": "other"}, {"Name": "dz-internal-2"}]
        ),
    )
    machines = machine_manager.list()
    assert len(machines) == 2
    assert machines[0]["Name"] == "dz-internal-1"
    assert machines[1]["Name"] == "dz-internal-2"
    assert rec_list.call_count() == 1


def test_run_raw_podman_command(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that run_raw_podman_command executes the command."""
    raw_command = ["info"]
    recorder = podman_register(raw_command)
    machine_manager.run_raw_podman_command(raw_command)
    assert recorder.call_count() == 1


def test_initialize_machine_with_timezone(
    machine_manager: PodmanMachineManager, podman_register: Callable
) -> None:
    """Test that the initialize_machine method runs the correct commands when no machine exists."""
    version = get_version()
    machine_name = f"dz-internal-{version}"
    image_path = str(machine_manager._get_machine_image_path())
    rec_list = podman_register(
        ["machine", "list", "--format", "json"], stdout=json.dumps([])
    )
    rec_init = podman_register(
        [
            "machine",
            "init",
            machine_name,
            "--image",
            image_path,
            "--timezone",
            "America/New_York",
        ]
    )
    machine_manager.init(timezone="America/New_York")
    assert rec_list.call_count() == 1
    assert rec_init.call_count() == 1
