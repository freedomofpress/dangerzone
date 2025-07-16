import logging
import platform
import sys
import time
import typing
from pathlib import Path
from typing import Callable, Optional

import requests

if typing.TYPE_CHECKING:
    from PySide2 import QtCore
else:
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide2 import QtCore

from dangerzone.gui.logic import DangerzoneGui
from dangerzone.gui.updater import check_for_updates_logic
from dangerzone.podman.machine import PodmanMachineManager
from dangerzone.settings import Settings
from dangerzone.updater import InstallationStrategy, get_installation_strategy
from dangerzone.updater.installer import Strategy, apply_installation_strategy
from dangerzone.updater.releases import EmptyReport, ErrorReport, ReleaseReport
from dangerzone.util import format_exception, get_resource_path, get_version

logger = logging.getLogger(__name__)


class ProgressReport:
    def __init__(self, message: str):
        self.message = message


class CompletionReport:
    def __init__(self, message: str, success: bool):
        self.message = message
        self.success = success


def install_container_logic(
    dangerzone: DangerzoneGui,
    installation_strategy: InstallationStrategy,
    callback: Callable[[str], None],
):
    if dangerzone.isolation_provider.requires_install():
        apply_installation_strategy(installation_strategy, callback=callback)


class BackgroundTask(QtCore.QThread):
    app_update_available = QtCore.Signal(str)
    container_update_available = QtCore.Signal()
    install_container_finished = QtCore.Signal(bool)
    status_report = QtCore.Signal(object)

    def __init__(self, dangerzone_gui):
        super().__init__()
        self.dangerzone_gui = dangerzone_gui
        self.settings = Settings()
        self.podman_machine_manager = PodmanMachineManager()

    def run(self):
        self.status_report.emit(ProgressReport("Starting"))

        if platform.system() in ["Windows", "Darwin"]:
            try:
                self.status_report.emit(ProgressReport("Initializing Podman machine"))
                self.podman_machine_manager.initialize_machine()
                self.status_report.emit(ProgressReport("Starting Podman machine"))
                self.podman_machine_manager.start_machine()
            except Exception as e:
                logger.exception("Failed to initialize Podman machine")
                self.status_report.emit(
                    CompletionReport(
                        "Failed to initialize Podman machine", success=False
                    )
                )
                return

        # Invoke logic for app and container updates
        updates_enabled = bool(self.settings.get("updater_check_all"))
        if updates_enabled:
            try:
                self.status_report.emit(ProgressReport("Checking for updates"))
                logger.info("Checking for application and container updates...")
                report = check_for_updates_logic(self.dangerzone_gui)
                if isinstance(report, ReleaseReport):
                    if report.new_github_release:
                        self.app_update_available.emit(report.version)
                    if report.container_image_bump:
                        self.container_update_available.emit()
            except Exception as e:
                logger.warning(
                    f"Failed to check for application and container updates: {e}"
                )
                self.status_report.emit(
                    CompletionReport(
                        "Failed to check for updates",
                        success=False,
                    )
                )
                return

        # Invoke logic for container image installation
        try:
            strategy = get_installation_strategy()
            if strategy != InstallationStrategy.DO_NOTHING:
                self.status_report.emit(ProgressReport("Installing container image"))
            apply_installation_strategy(strategy, callback=None)
            self.install_container_finished.emit(True)
        except Exception as e:
            logger.exception("Failed to install container")
            self.install_container_finished.emit(False)
            self.status_report.emit(
                CompletionReport("Failed to install container", success=False)
            )
            return

        logger.debug("Background task has finished")
        self.status_report.emit(CompletionReport("Ready", success=True))
