import platform
from typing import Optional

import pytest
from pytest_mock import MockerFixture

from dangerzone import errors, startup, wsl


class StartupSpy:
    def __init__(self, mocker: MockerFixture):
        self.mock_task = mocker.MagicMock()
        self.mock_task.should_skip.return_value = False
        self.runner = startup.StartupLogic(tasks=[self.mock_task])
        self.handle_start = mocker.spy(self.runner, "handle_start")
        self.handle_error = mocker.spy(self.runner, "handle_error")
        self.handle_success = mocker.spy(self.runner, "handle_success")


@pytest.fixture
def mock_startup_spy(mocker: MockerFixture) -> StartupSpy:
    return StartupSpy(mocker)


def test_startup_success(mock_startup_spy: StartupSpy) -> None:
    """A task runs to completion"""
    mock_startup_spy.runner.run()

    mock_startup_spy.handle_start.assert_called_once()
    mock_startup_spy.handle_success.assert_called_once()
    mock_startup_spy.handle_error.assert_not_called()
    mock_startup_spy.mock_task.handle_skip.assert_not_called()
    mock_startup_spy.mock_task.handle_start.assert_called_once()
    mock_startup_spy.mock_task.handle_error.assert_not_called()
    mock_startup_spy.mock_task.handle_success.assert_called_once()
    mock_startup_spy.mock_task.run.assert_called_once()


def test_startup_skip(mock_startup_spy: StartupSpy) -> None:
    """A task is skipped"""
    mock_startup_spy.mock_task.should_skip.return_value = True
    mock_startup_spy.runner.run()

    mock_startup_spy.handle_start.assert_called_once()
    mock_startup_spy.handle_success.assert_called_once()
    mock_startup_spy.handle_error.assert_not_called()
    mock_startup_spy.mock_task.handle_skip.assert_called_once()
    mock_startup_spy.mock_task.handle_start.assert_not_called()
    mock_startup_spy.mock_task.handle_error.assert_not_called()
    mock_startup_spy.mock_task.handle_success.assert_not_called()
    mock_startup_spy.mock_task.run.assert_not_called()


def test_startup_fail_allowed(mock_startup_spy: StartupSpy) -> None:
    """A task fails, and this is fine."""
    exc = Exception("failed")
    mock_startup_spy.mock_task.run.side_effect = exc
    mock_startup_spy.runner.run()

    mock_startup_spy.handle_start.assert_called_once()
    mock_startup_spy.handle_success.assert_called_once()
    mock_startup_spy.handle_error.assert_not_called()
    mock_startup_spy.mock_task.handle_skip.assert_not_called()
    mock_startup_spy.mock_task.handle_start.assert_called_once()
    mock_startup_spy.mock_task.handle_error.assert_called_with(exc)
    mock_startup_spy.mock_task.handle_success.assert_not_called()
    mock_startup_spy.mock_task.run.assert_called_once()


def test_startup_fail_not_allowed(mock_startup_spy: StartupSpy) -> None:
    """A task fails, and this is fatal."""
    exc = Exception("failed")
    mock_startup_spy.mock_task.run.side_effect = exc
    mock_startup_spy.mock_task.can_fail = False
    with pytest.raises(Exception):
        mock_startup_spy.runner.run()

    mock_startup_spy.handle_start.assert_called_once()
    mock_startup_spy.handle_success.assert_not_called()
    mock_startup_spy.handle_error.assert_called_once_with(
        mock_startup_spy.mock_task, exc
    )
    mock_startup_spy.mock_task.handle_skip.assert_not_called()
    mock_startup_spy.mock_task.handle_start.assert_called_once()
    mock_startup_spy.mock_task.handle_error.assert_called_with(exc)
    mock_startup_spy.mock_task.handle_success.assert_not_called()
    mock_startup_spy.mock_task.run.assert_called_once()


@pytest.mark.parametrize(
    "os_name, other_machines, setting, should_skip, raises_error, calls_prompt, calls_run",
    [
        ("Linux", False, "ask", True, False, False, False),
        ("Windows", False, "ask", True, False, False, False),
        ("Darwin", False, "ask", True, False, False, False),
        ("Darwin", True, "always", False, False, False, True),
        ("Darwin", True, "never", False, True, False, False),
        ("Darwin", True, "ask", False, False, True, True),
        ("Darwin", True, "ask", True, True, True, False),
    ],
)
def test_machine_stop_others_task(
    mocker: MockerFixture,
    os_name: str,
    other_machines: bool,
    setting: bool,
    should_skip: bool,
    raises_error: bool,
    calls_prompt: bool,
    calls_run: bool,
) -> None:
    mocker.patch("platform.system", return_value=os_name)
    mocker.patch("dangerzone.settings.Settings.get", return_value=setting)
    mock_podman_machine_manager = mocker.patch(
        "dangerzone.startup.PodmanMachineManager"
    ).return_value
    mock_prompt_user = mocker.patch(
        "dangerzone.startup.MachineStopOthersTask.prompt_user",
        return_value=not should_skip,
    )

    if other_machines:
        mock_podman_machine_manager.list_other_running_machines.side_effect = [
            ["other_machine"],
            ["other_machine"],
            [],
        ]
    else:
        mock_podman_machine_manager.list_other_running_machines.return_value = []

    task = startup.MachineStopOthersTask()
    run_spy = mocker.spy(task, "run")

    if raises_error:
        with pytest.raises(startup.errors.OtherMachineRunningError):
            task.should_skip()

        if calls_prompt:
            mock_prompt_user.assert_called_once()
        else:
            mock_prompt_user.assert_not_called()

        assert not calls_run
        run_spy.assert_not_called()
    else:
        assert task.should_skip() == should_skip
        if calls_prompt:
            mock_prompt_user.assert_called_once()
        else:
            mock_prompt_user.assert_not_called()

        if not should_skip:
            task.run()
            if calls_run:
                run_spy.assert_called_once()
                mock_podman_machine_manager.stop.assert_called_once_with(
                    name="other_machine"
                )
            else:
                run_spy.assert_not_called()
        else:
            run_spy.assert_not_called()
            mock_podman_machine_manager.stop.assert_not_called()


def test_startup_skips_podman_tasks_if_custom_runtime_is_specified(
    mocker: MockerFixture,
) -> None:
    """Skip Podman startup tasks when a custom runtime is specified."""
    mock_settings = mocker.patch("dangerzone.settings.Settings").return_value
    mock_settings.custom_runtime_specified.return_value = True
    mocker.patch(
        "dangerzone.startup.ContainerInstallTask.should_skip", return_value=True
    )
    mocker.patch("dangerzone.startup.UpdateCheckTask.should_skip", return_value=True)

    tasks = [
        startup.MachineInitTask(),
        startup.MachineStartTask(),
        startup.MachineStopOthersTask(),
        startup.ContainerInstallTask(),
        startup.UpdateCheckTask(),
    ]

    init_run_spy = mocker.spy(tasks[0], "run")
    init_skip_spy = mocker.spy(tasks[0], "should_skip")
    start_run_spy = mocker.spy(tasks[1], "run")
    start_skip_spy = mocker.spy(tasks[1], "should_skip")
    stop_others_run_spy = mocker.spy(tasks[2], "run")
    stop_others_skip_spy = mocker.spy(tasks[2], "should_skip")

    runner = startup.StartupLogic(tasks=tasks)
    runner.run()

    init_run_spy.assert_not_called()
    assert init_skip_spy.spy_return == True
    start_run_spy.assert_not_called()
    assert start_skip_spy.spy_return == True
    stop_others_run_spy.assert_not_called()
    assert stop_others_skip_spy.spy_return == True


@pytest.mark.parametrize("os_name", ["Linux", "Darwin"])
def test_wsl_install_task_should_skip_on_non_windows(
    mocker: MockerFixture, os_name: str
) -> None:
    """Test that WSLInstallTask is skipped on non-Windows OS."""
    mocker.patch("platform.system", return_value=os_name)
    task = startup.WSLInstallTask()
    assert task.should_skip() is True


def test_wsl_install_task_should_skip_if_wsl_installed(mocker: MockerFixture) -> None:
    """Test that WSLInstallTask is skipped if WSL is already installed."""
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.wsl.is_wsl_installed", return_value=True)
    task = startup.WSLInstallTask()
    assert task.should_skip() is True


def test_wsl_install_task_should_not_skip_if_wsl_not_installed_on_windows(
    mocker: MockerFixture,
) -> None:
    """Test that WSLInstallTask is not skipped if WSL is not installed on Windows."""
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.wsl.is_wsl_installed", return_value=False)
    task = startup.WSLInstallTask()
    assert task.should_skip() is False


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
def test_wsl_install_task_run_success(mocker: MockerFixture) -> None:
    """Test that WSLInstallTask run method raises WSLInstallNeedsReboot on success."""
    mocker.patch("dangerzone.wsl.is_wsl_installed", return_value=False)
    mock_install_wsl = mocker.patch(
        "dangerzone.wsl.install_wsl_and_check_reboot",
        side_effect=errors.WSLInstallNeedsReboot,
    )
    task = startup.WSLInstallTask()
    with pytest.raises(errors.WSLInstallNeedsReboot):
        task.run()
    mock_install_wsl.assert_called_once()


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific")
def test_wsl_install_task_run_failure(mocker: MockerFixture) -> None:
    """Test that WSLInstallTask run method raises WSLInstallFailed on failure."""
    mocker.patch("dangerzone.wsl.is_wsl_installed", return_value=False)
    mock_install_wsl = mocker.patch(
        "dangerzone.wsl.install_wsl_and_check_reboot",
        side_effect=errors.WSLInstallFailed,
    )
    task = startup.WSLInstallTask()
    with pytest.raises(errors.WSLInstallFailed):
        task.run()
    mock_install_wsl.assert_called_once()
