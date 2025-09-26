from .. import shutdown
from . import startup as gui_startup


class MachineStopTask(
    gui_startup.GUIMixin,
    shutdown.MachineStopTask,
    metaclass=gui_startup._MetaConflictResolver,
):
    pass


class ContainerStopTask(
    gui_startup.GUIMixin,
    shutdown.ContainerStopTask,
    metaclass=gui_startup._MetaConflictResolver,
):
    pass


class ShutdownThread(shutdown.ShutdownMixin, gui_startup.RunnerThread):
    pass
