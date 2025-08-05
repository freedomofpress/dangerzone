import abc
import logging
import platform
import typing

if typing.TYPE_CHECKING:
    from PySide2 import QtCore
else:
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide2 import QtCore


from . import settings
from .podman.machine import PodmanMachineManager
from .updater import (
    ErrorReport,
    InstallationStrategy,
    ReleaseReport,
    errors,
    installer,
    releases,
)

logger = logging.getLogger(__name__)


class Task(abc.ABC):
    can_fail = False

    def should_skip(self) -> bool:
        return False

    @abc.abstractproperty
    def name(self) -> str:
        pass

    def handle_skip(self) -> None:
        logger.info(f"Task '{self.name}' will be skipped")

    def handle_start(self) -> None:
        logger.info(f"Task '{self.name}' is starting...")

    def handle_error(self, e: Exception) -> None:
        """Handle task errors.

        Do not raise an exception here, so that the error handler of StartupLogic can
        run.
        """
        logger.error(f"Task '{self.name}' failed with error: {str(e)}", exc_info=e)

    def handle_success(self) -> None:
        logger.info(f"Task '{self.name}' completed successfully!")
        pass

    @abc.abstractmethod
    def run(self) -> None:
        pass


#############
# Basic tasks
#############


class MachineInitTask(Task):
    name = "Initializing Dangerzone VM"

    def should_skip(self) -> bool:
        return platform.system() == "Linux"

    def run(self) -> None:
        PodmanMachineManager().init()


class MachineStartTask(Task):
    name = "Starting Dangerzone VM"

    def should_skip(self) -> bool:
        return platform.system() == "Linux"

    def run(self) -> None:
        PodmanMachineManager().start()


class ContainerInstallTask(Task):
    name = "Configuring Dangerzone sandbox"

    def should_skip(self) -> bool:
        return installer.get_installation_strategy() == InstallationStrategy.DO_NOTHING

    def run(self) -> None:
        installer.install()


class UpdateCheckTask(Task):
    can_fail = True
    name = "Check for updates"

    def should_skip(self) -> bool:
        try:
            return not releases.should_check_for_updates(settings.Settings())
        except errors.NeedUserInput:
            self.prompt_user()
            return True

    def run(self) -> None:
        report = releases.check_for_updates(settings.Settings())
        if isinstance(report, ReleaseReport):
            if report.new_github_release:
                self.handle_app_update(report)
            if report.container_image_bump:
                self.handle_container_update(report)
        elif isinstance(report, ErrorReport):
            raise RuntimeError(report.error)

    def prompt_user(self) -> None:
        pass

    def handle_app_update(self, report: ReleaseReport) -> None:
        logger.info(f"Dangerzone {report.version} is out and can be installed")

    def handle_container_update(self, report: ReleaseReport) -> None:
        logger.info(f"There is an update for the Dangerzone sandbox")


class StartupLogic:
    def __init__(self, tasks: list[Task], raise_on_error: bool = True) -> None:
        self.tasks = tasks
        self.raise_on_error = raise_on_error
        super().__init__()

    def handle_start(self) -> None:
        logger.info("Performing some Dangerzone startup tasks")

    def handle_error(self, task: Task, e: Exception) -> None:
        logger.error(
            f"Stopping startup tasks because task '{task.name}' failed with an error"
        )
        if self.raise_on_error:
            raise e

    def handle_success(self) -> None:
        logger.info("Successfully finished all Dangerzone startup tasks")

    def run(self) -> None:
        self.handle_start()
        for task in self.tasks:
            if task.should_skip():
                task.handle_skip()
                continue
            task.handle_start()
            try:
                task.run()
            except Exception as e:
                task.handle_error(e)
                if not task.can_fail:
                    return self.handle_error(task, e)
            else:
                task.handle_success()
        self.handle_success()
