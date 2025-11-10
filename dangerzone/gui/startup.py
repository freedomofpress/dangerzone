import subprocess
import typing

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

from .. import startup
from ..updater import InstallationStrategy, installer
from ..updater.releases import EmptyReport, ErrorReport, ReleaseReport


class _MetaConflictResolver(type(QtCore.QObject), type(startup.Task)):  # type: ignore [misc]
    pass


class GUIMixin(QtCore.QObject):
    # XXX: There's some metaclass voodoo going on, and turns out that you have to define
    # signals at the class level, and subclasses do not share the same ones.
    skipped = QtCore.Signal()
    starting = QtCore.Signal()
    failed = QtCore.Signal(str)
    succeeded = QtCore.Signal()
    completed = QtCore.Signal()

    def __init__(self) -> None:
        QtCore.QObject.__init__(self)

    def handle_skip(self) -> None:
        self.skipped.emit()
        self.completed.emit()
        super().handle_skip()  # type: ignore [misc]

    def handle_start(self) -> None:
        self.starting.emit()
        super().handle_start()  # type: ignore [misc]

    def handle_error(self, e: Exception) -> None:
        self.failed.emit(str(e))
        super().handle_error(e)  # type: ignore [misc]

    def handle_success(self) -> None:
        self.succeeded.emit()
        self.completed.emit()
        super().handle_success()  # type: ignore [misc]


# GUI-fied basic tasks


class PromptRequest:
    """A request for prompting a user, with bidirectional input."""

    def __init__(self) -> None:
        self.req_data: typing.Any = None
        self.resp_data: typing.Any = None
        self.sem = QtCore.QSemaphore(0)

    def ask(
        self,
        signal: QtCore.SignalInstance,
        data: typing.Any = None,
    ) -> typing.Any:
        self.req_data = data
        signal.emit(self)
        self.sem.acquire()
        return self.resp_data

    def reply(self, data: typing.Any = None) -> None:
        self.resp_data = data
        self.sem.release()


class MachineStopOthersTask(
    GUIMixin, startup.MachineStopOthersTask, metaclass=_MetaConflictResolver
):
    needs_user_input = QtCore.Signal(object)  # PromptRequest

    def prompt_user(self, machine_name: str) -> bool:
        return PromptRequest().ask(self.needs_user_input, data={"name": machine_name})


class MachineInitTask(
    GUIMixin, startup.MachineInitTask, metaclass=_MetaConflictResolver
):
    pass


class MachineStartTask(
    GUIMixin, startup.MachineStartTask, metaclass=_MetaConflictResolver
):
    pass


class WSLInstallTask(GUIMixin, startup.WSLInstallTask, metaclass=_MetaConflictResolver):
    needs_reboot = QtCore.Signal(object)  # PromptRequest

    def handle_wsl_reboot(self, e: startup.errors.WSLInstallNeedsReboot) -> None:
        reboot = PromptRequest().ask(self.needs_reboot)
        if reboot:
            subprocess.run(["shutdown", "/r", "/t", "0"])
            # The OS is about to reboot, so there's no need to continue with the
            # shutdown sequence.
            raise e
        else:
            # The user chose to quit, so we should exit gracefully.
            raise SystemExit(0)


class ContainerInstallTask(
    GUIMixin, startup.ContainerInstallTask, metaclass=_MetaConflictResolver
):
    load_container = QtCore.Signal()
    download_container = QtCore.Signal()

    def run(self) -> None:
        strategy = installer.get_installation_strategy()
        if strategy == InstallationStrategy.INSTALL_LOCAL_CONTAINER:
            self.load_container.emit()
        elif strategy == InstallationStrategy.INSTALL_REMOTE_CONTAINER:
            self.download_container.emit()
        return super().run()


class UpdateCheckTask(
    GUIMixin, startup.UpdateCheckTask, metaclass=_MetaConflictResolver
):
    needs_user_input = QtCore.Signal()
    app_update_available = QtCore.Signal(object)
    container_update_available = QtCore.Signal(object)

    def prompt_user(self) -> None:
        super().prompt_user()
        self.needs_user_input.emit()

    def handle_app_update(self, report: ReleaseReport) -> None:
        self.app_update_available.emit(report)
        super().handle_app_update(report)

    def handle_container_update(self, report: ReleaseReport) -> None:
        self.container_update_available.emit(report)
        super().handle_container_update(report)


class RunnerThread(startup.Runner, QtCore.QThread):
    starting = QtCore.Signal()
    failed = QtCore.Signal(str)
    succeeded = QtCore.Signal()

    def handle_start(self) -> None:
        self.starting.emit()
        super().handle_start()

    def handle_error(self, task: startup.Task, e: Exception) -> None:
        self.failed.emit(str(e))
        super().handle_error(task, e)

    def handle_success(self) -> None:
        self.succeeded.emit()
        super().handle_success()


class StartupThread(startup.StartupMixin, RunnerThread):
    pass
