import sys

from PySide6 import QtCore
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


class Application(QApplication):
    document_selected = QtCore.Signal(str)
    new_window = QtCore.Signal()
    application_activated = QtCore.Signal()

    def __init__(self):
        super(Application, self).__init__()
        self.setQuitOnLastWindowClosed(False)
        self.original_event = self.event

        def monkeypatch_event(event: QEvent):
            # In macOS, handle the file open event
            if event.type() == QtCore.QEvent.FileOpen:
                # Skip file open events in dev mode
                if not hasattr(sys, "dangerzone_dev"):
                    self.document_selected.emit(event.file())
                    return True
            elif event.type() == QtCore.QEvent.ApplicationActivate:
                self.application_activated.emit()
                return True
            return self.original_event(event)

        self.event = monkeypatch_event
