import logging
import typing

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

from dangerzone.gui.widgets import TracebackWidget


class LogHandler(logging.Handler, QtCore.QObject):
    """Capture application logs and emit them as signals.

    This Qt object is responsible for capturing all application logs, and emitting them
    as signals, so that other widgets can show them to the user.
    """

    new_record = QtCore.Signal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg + "\n")


class LogWindow(QtWidgets.QDialog):
    """Show logs and startup activity.

    Define a widget where the user can see more details about the following:
    * Application logs
    * Status of startup tasks
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dangerzone Background Task Logs")
        self.setMinimumSize(600, 400)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setOpenExternalLinks(True)
        self.label.setWordWrap(True)

        self.traceback_widget = TracebackWidget()
        self.traceback_widget.setVisible(True)  # Always visible in the log window

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.traceback_widget)
        self.setLayout(layout)

    def handle_startup_begin(self):
        self.label.setText("Dangerzone is starting up...")

    def handle_task_machine_init(self):
        self.label.setText(
            "Initializing the Dangerzone VM<br>This might take a few minutes..."
        )

    def handle_task_machine_start(self):
        self.label.setText("Starting the Dangerzone VM...")

    def handle_task_update_check(self):
        self.label.setText("Checking for updates...")

    def handle_task_container_install(self):
        self.label.setText(
            "Installing the Dangerzone container sandbox<br>"
            "This might take a few minutes..."
        )

    def handle_task_machine_init_failed(self, error):
        self.label.setText("Initializing the Dangerzone VM... failed")

    def handle_task_machine_start_failed(self, error):
        self.label.setText("Starting the Dangerzone VM... failed")

    def handle_task_update_check_failed(self, error):
        self.label.setText("Checking for updates... failed")

    def handle_task_container_install_failed(self, error):
        self.label.setText("Installing container sandbox... failed")

    def append_log(self, line: str):
        self.traceback_widget.process_output(line)
