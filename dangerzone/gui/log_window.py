import logging

from PySide6 import QtCore, QtWidgets

from dangerzone.gui.widgets import TracebackWidget


class LogHandler(logging.Handler, QtCore.QObject):
    new_record = QtCore.Signal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg + "\n")


class LogWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dangerzone Background Task Logs")
        self.setMinimumSize(600, 400)

        self.traceback_widget = TracebackWidget()
        self.traceback_widget.setVisible(True)  # Always visible in the log window

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.traceback_widget)
        self.setLayout(layout)

    def append_log(self, line: str):
        self.traceback_widget.process_output(line)
