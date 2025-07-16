import logging
import platform

from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui.background_task import (
    BackgroundTask,
    CompletionReport,
    ProgressReport,
)
from dangerzone.updater import InstallationStrategy
from dangerzone.updater.releases import ReleaseReport

logger = logging.getLogger(__name__)


def test_background_task_podman_machine_management(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    """Test that the Podman machine is initialized and started."""
    # Mock the platform to be Windows or Darwin
    mocker.patch("platform.system", return_value="Windows")

    # Mock the PodmanMachineManager
    mock_podman_machine_manager = mocker.MagicMock()
    background_task.podman_machine_manager = mock_podman_machine_manager

    # Mock installation strategy to do nothing
    mocker.patch(
        "dangerzone.gui.background_task.get_installation_strategy",
        return_value=InstallationStrategy.DO_NOTHING,
    )

    reports = []
    background_task.status_report.connect(reports.append)

    background_task.start()
    background_task.wait()

    mock_podman_machine_manager.initialize_machine.assert_called_once()
    mock_podman_machine_manager.start_machine.assert_called_once()

    qtbot.waitUntil(lambda: len(reports) == 4)
    assert isinstance(reports[0], ProgressReport)
    assert reports[0].message == "Starting"
    assert isinstance(reports[1], ProgressReport)
    assert reports[1].message == "Initializing Podman machine"
    assert isinstance(reports[2], ProgressReport)
    assert reports[2].message == "Starting Podman machine"
    assert isinstance(reports[3], CompletionReport)
    assert reports[3].message == "Ready"
    assert reports[3].success is True


def test_background_task_app_update_check_success(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    """Test that the app update signal is emitted when an update is available."""
    mocker.patch("platform.system", return_value="Linux")
    # Enable app updates in settings
    background_task.settings.set("updater_check_all", True)

    # Mock update check to return a new version
    mocker.patch(
        "dangerzone.gui.background_task.check_for_updates_logic",
        return_value=ReleaseReport("1.2.3", "changelog", container_image_bump=False),
    )
    # Mock installation strategy to do nothing
    mocker.patch(
        "dangerzone.gui.background_task.get_installation_strategy",
        return_value=InstallationStrategy.DO_NOTHING,
    )

    reports = []
    background_task.status_report.connect(reports.append)

    with qtbot.waitSignal(background_task.app_update_available) as app_blocker:
        background_task.start()
        background_task.wait()

    assert app_blocker.args == ["1.2.3"]

    qtbot.waitUntil(lambda: len(reports) == 3)
    assert isinstance(reports[0], ProgressReport)
    assert reports[0].message == "Starting"
    assert isinstance(reports[1], ProgressReport)
    assert reports[1].message == "Checking for updates"
    assert isinstance(reports[2], CompletionReport)
    assert reports[2].message == "Ready"
    assert reports[2].success is True


def test_background_task_app_update_check_failure(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    """Test the status report on update check failure."""
    mocker.patch("platform.system", return_value="Linux")
    # Enable app updates
    background_task.settings.set("updater_check_all", True)

    # Mock update check to fail
    mocker.patch(
        "dangerzone.gui.background_task.check_for_updates_logic",
        side_effect=Exception("Update check failed"),
    )

    reports = []
    background_task.status_report.connect(reports.append)

    background_task.start()
    background_task.wait()

    # FIXME: Check that app_update signal somehow returns an error.

    qtbot.waitUntil(lambda: len(reports) == 3)
    assert isinstance(reports[0], ProgressReport)
    assert reports[0].message == "Starting"
    assert isinstance(reports[1], ProgressReport)
    assert reports[1].message == "Checking for updates"
    assert isinstance(reports[2], CompletionReport)
    assert reports[2].message == "Failed to check for updates"
    assert reports[2].success is False


def test_background_task_container_install_success(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    """Test that the install finished signal is emitted on success."""
    mocker.patch("platform.system", return_value="Linux")
    # Disable app updates to focus on installation
    background_task.settings.set("updater_check_all", False)

    # Mock installation strategy to require an install
    mocker.patch(
        "dangerzone.gui.background_task.get_installation_strategy",
        return_value=InstallationStrategy.INSTALL_REMOTE_CONTAINER,
    )
    # Mock the actual installation to be successful
    mock_apply_strategy = mocker.patch(
        "dangerzone.gui.background_task.apply_installation_strategy"
    )

    reports = []
    background_task.status_report.connect(reports.append)

    with qtbot.waitSignal(background_task.install_container_finished) as blocker:
        background_task.start()
        background_task.wait()

    assert blocker.args == [True]
    mock_apply_strategy.assert_called_once()

    qtbot.waitUntil(lambda: len(reports) == 3)
    assert isinstance(reports[0], ProgressReport)
    assert reports[0].message == "Starting"
    assert isinstance(reports[1], ProgressReport)
    assert reports[1].message == "Installing container image"
    assert isinstance(reports[2], CompletionReport)
    assert reports[2].message == "Ready"
    assert reports[2].success is True


def test_background_task_container_install_failure(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    """Test that the install finished signal is emitted on failure."""
    mocker.patch("platform.system", return_value="Linux")
    # Disable app updates to focus on installation
    background_task.settings.set("updater_check_all", False)

    # Mock installation strategy to require an install
    mocker.patch(
        "dangerzone.gui.background_task.get_installation_strategy",
        return_value=InstallationStrategy.INSTALL_REMOTE_CONTAINER,
    )
    # Mock the actual installation to fail
    mock_apply_strategy = mocker.patch(
        "dangerzone.gui.background_task.apply_installation_strategy",
        side_effect=Exception("Installation failed"),
    )

    reports = []
    background_task.status_report.connect(reports.append)

    with qtbot.waitSignal(background_task.install_container_finished) as blocker:
        background_task.start()
        background_task.wait()

    assert blocker.args == [False]
    mock_apply_strategy.assert_called_once()

    qtbot.waitUntil(lambda: len(reports) == 3)
    assert isinstance(reports[0], ProgressReport)
    assert reports[0].message == "Starting"
    assert isinstance(reports[1], ProgressReport)
    assert reports[1].message == "Installing container image"
    assert isinstance(reports[2], CompletionReport)
    assert reports[2].message == "Failed to install container"
    assert reports[2].success is False
