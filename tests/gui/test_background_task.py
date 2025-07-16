import logging
import platform
import time
import typing
from typing import List
from unittest.mock import MagicMock

from pytest import fixture
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui.background_task import BackgroundTask
from dangerzone.gui.logic import DangerzoneGui
from dangerzone.settings import Settings
from dangerzone.updater.installer import Strategy
from dangerzone.updater.releases import EmptyReport, ErrorReport, ReleaseReport

logger = logging.getLogger(__name__)


def test_background_task_app_update_check(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    # Enable app updates in settings
    background_task.settings.set("updater_check_all", True)

    # Mock check_for_updates_logic to simulate an app update available
    mocker.patch(
        "dangerzone.gui.background_task.check_for_updates_logic",
        return_value=ReleaseReport("1.2.3", "changelog", container_image_bump=False),
    )

    # Mock get_version to be different from the new version
    mocker.patch("dangerzone.util.get_version", return_value="1.2.2")

    # def test(app_update_available):
    #     return app_update_available == "1.2.3"

    # signals = [
    #     (background_task.app_update_available, "app_update_available"),
    #     # (background_task.finished, "finished"),
    # ]
    # # callbacks = [test, None]
    # callbacks = [test]

    # with qtbot.waitSignals(signals, check_params_cbs=callbacks) as blocker:
    #     background_task.start()
    # background_task.wait()
    with qtbot.waitSignal(background_task.app_update_available) as app_blocker:
        with qtbot.waitSignal(background_task.finished) as fin_blocker:
            background_task.start()
        assert app_blocker.args[0] == "1.2.3"
    background_task.wait()


def test_background_task_install_container_success(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    # Mock install_container_logic to simulate success
    mock_install = mocker.patch(
        "dangerzone.gui.background_task.install", return_value=None
    )

    # Mock check_for_updates_logic to simulate an app update available
    mocker.patch(
        "dangerzone.gui.background_task.check_for_updates_logic",
        return_value=ReleaseReport(None, None, container_image_bump=True),
    )

    with qtbot.waitSignal(background_task.install_container_finished) as con_blocker:
        with qtbot.waitSignal(background_task.finished) as fin_blocker:
            background_task.start()
        assert con_blocker.args[0] is True
    background_task.wait()

    mock_install.assert_called_once()


def test_background_task_install_container_failure(
    qtbot: QtBot, background_task: BackgroundTask, mocker: MockerFixture
) -> None:
    # Mock install_container_logic to simulate success
    mock_install = mocker.patch(
        "dangerzone.gui.background_task.install",
        side_effect=Exception("Installation failed"),
    )

    # Mock check_for_updates_logic to simulate an app update available
    mocker.patch(
        "dangerzone.gui.background_task.check_for_updates_logic",
        return_value=ReleaseReport(None, None, container_image_bump=True),
    )

    with qtbot.waitSignal(background_task.install_container_finished) as con_blocker:
        with qtbot.waitSignal(background_task.finished) as fin_blocker:
            background_task.start()
        assert con_blocker.args[0] is False
    background_task.wait()

    mock_install.assert_called_once()
