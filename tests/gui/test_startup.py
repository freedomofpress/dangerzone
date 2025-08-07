from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot

from dangerzone.gui import startup
from dangerzone.startup import MachineInitTask, MachineStartTask, Task
from dangerzone.updater import ErrorReport, InstallationStrategy, ReleaseReport
from dangerzone.updater import errors as update_errors


class StartupThreadMocker(startup.StartupThread):
    def __init__(self, qtbot: QtBot, mocker: MockerFixture):
        self.qtbot = qtbot
        self.mocker = mocker
        self.task_machine_init = startup.MachineInitTask()
        self.task_machine_start = startup.MachineStartTask()
        self.task_update_check = startup.UpdateCheckTask()
        self.task_container_install = startup.ContainerInstallTask()
        self.tasks = [
            self.task_machine_init,
            self.task_machine_start,
            self.task_update_check,
            self.task_container_install,
        ]
        self.startup_thread = startup.StartupThread(self.tasks, raise_on_error=False)
        self.expected_signals = []
        self.not_expected_funcs = []

    def make_machine_task_succeed(self):
        self.mocker.patch("platform.system", return_value="Windows")
        self.mocker.patch("dangerzone.startup.PodmanMachineManager")

    def make_machine_task_skip(self):
        self.mocker.patch("platform.system", return_value="Linux")

    def make_machine_task_fail(self):
        self.mocker.patch("platform.system", return_value="Windows")
        self.mocker.patch(
            "dangerzone.startup.PodmanMachineManager",
            side_effect=Exception("Forcing task to fail"),
        )

    def make_update_task_succeed(self):
        self.mocker.patch(
            "dangerzone.updater.releases.should_check_for_updates", return_value=True
        )
        self.mocker.patch("dangerzone.updater.releases.check_for_updates")

    def make_update_task_skip(self):
        self.mocker.patch(
            "dangerzone.updater.releases.should_check_for_updates", return_value=False
        )

    def make_update_task_fail(self):
        self.mocker.patch(
            "dangerzone.updater.releases.should_check_for_updates", return_value=True
        )
        self.mocker.patch(
            "dangerzone.updater.releases.check_for_updates",
            side_effect=Exception("Forcing task to fail"),
        )

    def make_install_task_succeed(self):
        self.mocker.patch(
            "dangerzone.updater.installer.get_installation_strategy",
            return_value=InstallationStrategy.INSTALL_LOCAL_CONTAINER,
        )
        self.mocker.patch("dangerzone.updater.installer.install")

    def make_install_task_skip(self):
        self.mocker.patch(
            "dangerzone.updater.installer.get_installation_strategy",
            return_value=InstallationStrategy.DO_NOTHING,
        )

    def make_install_task_fail(self):
        self.mocker.patch(
            "dangerzone.updater.installer.get_installation_strategy",
            return_value=InstallationStrategy.INSTALL_LOCAL_CONTAINER,
        )
        self.mocker.patch(
            "dangerzone.updater.installer.install",
            side_effect=Exception("Forcing task to fail"),
        )

    def expect_tasks_succeed(self, tasks=list[Task]):
        for task in tasks:
            if isinstance(task, (MachineInitTask, MachineStartTask)):
                self.make_machine_task_succeed()
            elif isinstance(task, startup.UpdateCheckTask):
                self.make_update_task_succeed()
            elif isinstance(task, startup.ContainerInstallTask):
                self.make_install_task_succeed()
            else:
                raise RuntimeError(f"Unexpected task: {task}")

            names = ["starting", "succeeded", "completed"]
            for name in names:
                self.expected_signals.append(
                    (getattr(task, name), f"{task.__class__.__name__}.{name}")
                )
            task.handle_skip = self.mocker.MagicMock()
            self.not_expected_funcs.append(task.handle_skip)
            task.handle_error = self.mocker.MagicMock()
            self.not_expected_funcs.append(task.handle_error)

    def expect_tasks_skip(self, tasks=list[Task]):
        for task in tasks:
            if isinstance(task, (MachineInitTask, MachineStartTask)):
                self.make_machine_task_skip()
            elif isinstance(task, startup.UpdateCheckTask):
                self.make_update_task_skip()
            elif isinstance(task, startup.ContainerInstallTask):
                self.make_install_task_skip()
            else:
                raise RuntimeError(f"Unexpected task: {task}")

            names = ["skipped", "completed"]
            for name in names:
                self.expected_signals.append(
                    (getattr(task, name), f"{task.__class__.__name__}.{name}")
                )
            task.handle_start = self.mocker.MagicMock()
            self.not_expected_funcs.append(task.handle_start)
            task.handle_error = self.mocker.MagicMock()
            self.not_expected_funcs.append(task.handle_error)

    def expect_tasks_fail(self, tasks=list[Task]):
        for task in tasks:
            if isinstance(task, (MachineInitTask, MachineStartTask)):
                self.make_machine_task_fail()
            elif isinstance(task, startup.UpdateCheckTask):
                self.make_update_task_fail()
            elif isinstance(task, startup.ContainerInstallTask):
                self.make_install_task_fail()
            else:
                raise RuntimeError(f"Unexpected task: {task}")

            names = ["starting", "failed"]
            for name in names:
                self.expected_signals.append(
                    (getattr(task, name), f"{task.__class__.__name__}.{name}")
                )
            task.handle_skip = self.mocker.MagicMock()
            self.not_expected_funcs.append(task.handle_skip)

    def expect_startup_succeed(self):
        self.expected_signals += [
            (self.startup_thread.starting, "StartupThread.starting"),
            (self.startup_thread.succeeded, "StartupThread.succeeded"),
        ]
        self.startup_thread.handle_error = self.mocker.MagicMock()
        self.not_expected_funcs.append(self.startup_thread.handle_error)

    def expect_startup_fail(self):
        self.expected_signals += [
            (self.startup_thread.starting, "StartupThread.starting"),
            (self.startup_thread.failed, "StartupThread.failed"),
        ]
        self.startup_thread.handle_success = self.mocker.MagicMock()
        self.not_expected_funcs.append(self.startup_thread.handle_success)

    def check_run(self):
        with self.qtbot.waitSignals(self.expected_signals):
            self.startup_thread.start()
            self.startup_thread.wait()

        for func in self.not_expected_funcs:
            func.assert_not_called()


def test_startup_all_success(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(startup_thread.tasks)
    startup_thread.expect_startup_succeed()
    startup_thread.check_run()


def test_startup_all_skip(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_skip(startup_thread.tasks)
    startup_thread.expect_startup_succeed()
    startup_thread.check_run()


def test_startup_machine_init_fail(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_fail([startup_thread.task_machine_init])
    startup_thread.expect_startup_fail()
    startup_thread.check_run()


def test_startup_machine_start_fail(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    # NOTE: Make machine_init allowed to fail, so that we can proceed to the
    # machine_start task.
    startup_thread.task_machine_init.can_fail = True
    startup_thread.expect_tasks_fail(
        [startup_thread.task_machine_init, startup_thread.task_machine_start]
    )
    startup_thread.expect_startup_fail()
    startup_thread.check_run()


def test_startup_update_check_fail(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(
        [startup_thread.task_machine_init, startup_thread.task_machine_start]
    )
    startup_thread.expect_tasks_fail([startup_thread.task_update_check])
    startup_thread.expect_tasks_skip([startup_thread.task_container_install])
    # NOTE: The update check task is a special case, where a failure does not mean that
    # startup will fail as a whole.
    startup_thread.expect_startup_succeed()
    startup_thread.check_run()


def test_startup_update_check_needs_user_input(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(
        [
            startup_thread.task_machine_init,
            startup_thread.task_machine_start,
        ]
    )
    startup_thread.expect_tasks_skip(
        [
            startup_thread.task_update_check,
            startup_thread.task_container_install,
        ]
    )
    startup_thread.expect_startup_succeed()

    mocker.patch(
        "dangerzone.updater.releases.should_check_for_updates",
        side_effect=update_errors.NeedUserInput(),
    )
    startup_thread.expected_signals.append(
        (
            startup_thread.task_update_check.needs_user_input,
            "UpdateCheckTask.needs_user_input",
        )
    )
    startup_thread.check_run()


def test_startup_update_check_app_update(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(
        [
            startup_thread.task_machine_init,
            startup_thread.task_machine_start,
            startup_thread.task_update_check,
        ]
    )
    startup_thread.expect_tasks_skip([startup_thread.task_container_install])
    startup_thread.expect_startup_succeed()

    mocker.patch(
        "dangerzone.updater.releases.check_for_updates",
        return_value=ReleaseReport(version="0.9.9"),
    )
    startup_thread.expected_signals.append(
        (
            startup_thread.task_update_check.app_update_available,
            "UpdateCheckTask.app_update_available",
        )
    )
    startup_thread.check_run()


def test_startup_update_check_container_update(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(
        [
            startup_thread.task_machine_init,
            startup_thread.task_machine_start,
            startup_thread.task_update_check,
        ]
    )
    startup_thread.expect_tasks_skip([startup_thread.task_container_install])
    startup_thread.expect_startup_succeed()

    mocker.patch(
        "dangerzone.updater.releases.check_for_updates",
        return_value=ReleaseReport(container_image_bump=True),
    )
    startup_thread.expected_signals.append(
        (
            startup_thread.task_update_check.container_update_available,
            "UpdateCheckTask.container_update_available",
        )
    )
    startup_thread.check_run()


def test_startup_container_install_fail(qtbot: QtBot, mocker: MockerFixture):
    startup_thread = StartupThreadMocker(qtbot, mocker)
    startup_thread.expect_tasks_succeed(
        [
            startup_thread.task_machine_init,
            startup_thread.task_machine_start,
            startup_thread.task_update_check,
        ]
    )
    startup_thread.expect_tasks_fail([startup_thread.task_container_install])
    startup_thread.expect_startup_fail()
    startup_thread.check_run()
