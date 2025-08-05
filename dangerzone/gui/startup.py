import typing

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

from .. import startup
from ..updater.releases import EmptyReport, ErrorReport, ReleaseReport


class _MetaConflictResolver(type(QtCore.QObject), type(startup.Task)):
    pass


class GUIMixin(QtCore.QObject):
    # XXX: There's some metaclass voodoo going on, and turns out that you have to define
    # signals at the class level, and subclasses do not share the same ones.
    skipped = QtCore.Signal()
    starting = QtCore.Signal()
    failed = QtCore.Signal(str)
    succeeded = QtCore.Signal()
    completed = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)

    def handle_skip(self):
        self.skipped.emit()
        self.completed.emit()
        super().handle_skip()

    def handle_start(self):
        self.starting.emit()
        super().handle_start()

    def handle_error(self, e):
        self.failed.emit(str(e))
        super().handle_error(e)

    def handle_success(self):
        self.succeeded.emit()
        self.completed.emit()
        super().handle_success()


# GUI-fied basic tasks


class MachineInitTask(
    GUIMixin, startup.MachineInitTask, metaclass=_MetaConflictResolver
):
    pass


class MachineStartTask(
    GUIMixin, startup.MachineStartTask, metaclass=_MetaConflictResolver
):
    pass


class ContainerInstallTask(
    GUIMixin, startup.ContainerInstallTask, metaclass=_MetaConflictResolver
):
    pass


class UpdateCheckTask(
    GUIMixin, startup.UpdateCheckTask, metaclass=_MetaConflictResolver
):
    needs_user_input = QtCore.Signal()
    app_update_available = QtCore.Signal(object)
    container_update_available = QtCore.Signal(object)

    def prompt_user(self):
        super().prompt_user()
        self.needs_user_input.emit()

    def handle_app_update(self, report: ReleaseReport):
        self.app_update_available.emit(report)
        super().handle_app_update(report)

    def handle_container_update(self, report: ReleaseReport):
        self.container_update_available.emit(report)
        super().handle_container_update(report)


class StartupThread(startup.StartupLogic, QtCore.QThread):
    starting = QtCore.Signal()
    failed = QtCore.Signal(str)
    succeeded = QtCore.Signal()

    def handle_start(self):
        self.starting.emit()
        super().handle_start()

    def handle_error(self, task, e):
        self.failed.emit(str(e))
        super().handle_error(task, e)

    def handle_success(self):
        self.succeeded.emit()
        super().handle_success()
