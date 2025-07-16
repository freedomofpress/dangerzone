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
from dangerzone.settings import Settings
from dangerzone.updater import InstallationStrategy, install
from dangerzone.updater.installer import Strategy, apply_installation_strategy
from dangerzone.updater.releases import EmptyReport, ErrorReport, ReleaseReport
from dangerzone.util import format_exception, get_resource_path, get_version

logger = logging.getLogger(__name__)


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
    finished = QtCore.Signal()

    def __init__(self, dangerzone_gui):
        super().__init__()
        self.dangerzone_gui = dangerzone_gui
        self.settings = Settings()

    def run(self):
        # Invoke logic for app and container updates
        updates_enabled = bool(self.settings.get("updater_check_all"))
        if updates_enabled:
            try:
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

        # Invoke logic for container image installation
        try:
            # FIXME: Add callback
            install(callback=None)
            self.install_container_finished.emit(True)
        except Exception as e:
            logger.exception("Failed to install container")
            self.install_container_finished.emit(False)

        logger.debug("Background task has finished")
        self.finished.emit()
