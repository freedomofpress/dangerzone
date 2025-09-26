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


from . import errors, settings
from .podman.machine import PodmanMachineManager
from .updater import (
    ErrorReport,
    InstallationStrategy,
    ReleaseReport,
    installer,
    releases,
)
from .updater import (
    errors as updater_errors,
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


class MachineStopOthersTask(Task):
    name = "Stopping other Podman VMs"

    def fail(self, message: str):  # type: ignore [no-untyped-def]
        raise errors.OtherMachineRunningError(message)

    def should_skip(self) -> bool:
        if platform.system() in ["Linux", "Windows"]:
            # * On Linux, there are no Podman machines
            # * On Windows, WSL allows multiple VMs:
            #   https://github.com/containers/podman/issues/18415
            # * On macOS, only one Podman machine can run:
            #   https://docs.podman.io/en/v5.2.2/markdown/podman-machine-start.1.html
            return True

        other_running_machines = PodmanMachineManager().list_other_running_machines()
        if not other_running_machines:
            return True
        assert len(other_running_machines) == 1
        machine_name = other_running_machines[0]
        logger.info(
            f"Dangerzone has detected that a Podman machine with name '{machine_name}'"
            " is already running in your system. This machine needs to stop so that"
            " Dangerzone can run."
        )

        stop_setting = settings.Settings().get("stop_other_podman_machines")

        if stop_setting == "always":
            logger.info(
                "Stopping the Podman machine because the user has asked us to remember their choice"
            )
            return False
        elif stop_setting == "never":
            self.fail(
                "Another Podman machine is running and Dangerzone is configured to not stop it."
            )
        elif stop_setting == "ask":
            logger.debug("We need to prompt the user to stop the other Podman machine")
            stop = self.prompt_user(machine_name)
            if not stop:
                self.fail(
                    f"User decided to quit Dangerzone instead of stopping Podman"
                    f" machine '{machine_name}'."
                )
                # NOTE: This is required only for testing. Else, we expect it will raise
                # an exception.
                return True
            else:
                return False

        raise Exception(
            "BUG: Dangerzone cannot decide how to handle running Podman machine"
        )

    def prompt_user(self, machine_name: str) -> bool:
        """Return whether the user has accepted to stop the machine or not."""
        return self.fail(
            f"Dangerzone has detected that a Podman machine with name '{machine_name}'"
            " is already running in the system, but cannot prompt the user to stop it."
        )

    def run(self) -> None:
        other_running_machines = PodmanMachineManager().list_other_running_machines()
        for machine_name in other_running_machines:
            logger.info(f"Stopping other Podman machine: {machine_name}")
            PodmanMachineManager().stop(name=machine_name)

        # Verify no other machines are running
        if PodmanMachineManager().list_other_running_machines():
            raise RuntimeError("Failed to stop all other running Podman machines.")


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
        except updater_errors.NeedUserInput:
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


class Runner:
    def __init__(self, tasks: list[Task], raise_on_error: bool = True) -> None:
        self.tasks = tasks
        self.raise_on_error = raise_on_error
        super().__init__()

    def handle_start_custom(self) -> None:
        pass

    def handle_error_custom(self, task: Task, e: Exception) -> None:
        pass

    def handle_success_custom(self) -> None:
        pass

    def handle_start(self) -> None:
        self.handle_start_custom()

    def handle_error(self, task: Task, e: Exception) -> None:
        self.handle_error_custom(task, e)
        if self.raise_on_error:
            raise e

    def handle_success(self) -> None:
        self.handle_success_custom()

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


class StartupMixin:
    def handle_start_custom(self) -> None:
        logger.info("Performing some Dangerzone startup tasks")

    def handle_error_custom(self, task: Task, e: Exception) -> None:
        logger.error(
            f"Stopping startup tasks because task '{task.name}' failed with an error"
        )

    def handle_success_custom(self) -> None:
        logger.info("Successfully finished all Dangerzone startup tasks")


class StartupLogic(Runner, StartupMixin):
    pass
