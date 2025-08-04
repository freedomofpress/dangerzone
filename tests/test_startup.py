from typing import Optional

import pytest
from pytest_mock import MockerFixture

from dangerzone import startup


class StartupSpy:
    def __init__(
        self, mocker: MockerFixture, tasks: Optional[list[startup.Task]] = None
    ):
        if tasks:
            self.runner = startup.StartupLogic(tasks=[mock_task])
        else:
            self.mock_task = mocker.MagicMock()
            self.mock_task.should_skip.return_value = False
            self.runner = startup.StartupLogic(tasks=[self.mock_task])
        self.handle_start = mocker.spy(self.runner, "handle_start")
        self.handle_error = mocker.spy(self.runner, "handle_error")
        self.handle_success = mocker.spy(self.runner, "handle_success")


@pytest.fixture
def mock_startup_spy(mocker: MockerFixture) -> StartupSpy:
    return StartupSpy(mocker)


def test_startup_success(mock_startup_spy: StartupSpy):
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


def test_startup_skip(mock_startup_spy: StartupSpy):
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


def test_startup_fail_allowed(mock_startup_spy: StartupSpy):
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


def test_startup_fail_not_allowed(mock_startup_spy: StartupSpy):
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
