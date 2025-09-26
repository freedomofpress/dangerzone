import logging
import platform
import typing

from . import container_utils, startup
from .podman.machine import PodmanMachineManager

logger = logging.getLogger(__name__)


class MachineStopTask(startup.Task):
    can_fail = True
    name = "Stopping Dangerzone VM"

    def should_skip(self) -> bool:
        return platform.system() == "Linux"

    def run(self) -> None:
        PodmanMachineManager().stop()


class ContainerStopTask(startup.Task):
    can_fail = True
    name = "Stopping the sandbox"

    def run(self) -> None:
        # In practice, we don't expect more than 1 container in flight.
        for cont in container_utils.list_containers():
            container_utils.kill_container(cont)


class ShutdownMixin:
    def handle_start_custom(self) -> None:
        logger.info("Shutting down Dangerzone")

    def handle_error_custom(self, task: startup.Task, e: Exception) -> None:
        logger.error(
            f"Encountered an error in task '{task.name}', while shutting down Dangerzone."
            f" Resuming..."
        )

    def handle_success_custom(self) -> None:
        logger.info("Dangerzone's shutdown tasks have finished successfully")


class ShutdownLogic(startup.Runner, ShutdownMixin):
    pass
