import logging
import typing
from typing import Optional

if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets

from dangerzone.gui.widgets import TracebackWidget


class LogSignal(QtCore.QObject):
    new_record = QtCore.Signal(str)


class LogHandler(logging.Handler):
    """Capture application logs and emit them as signals.

    This Qt object is responsible for capturing all application logs, and emitting them
    as signals, so that other widgets can show them to the user.
    """

    def __init__(self) -> None:
        super().__init__()
        self._log_signal = LogSignal()

    @property
    def new_record(self) -> QtCore.SignalInstance:
        return self._log_signal.new_record

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._log_signal.new_record.emit(msg + "\n")


class LogWindow(QtWidgets.QDialog):
    """Show logs and startup activity.

    Define a widget where the user can see more details about the following:
    * Application logs
    * Status of startup tasks
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
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

    def handle_startup_begin(self) -> None:
        self.label.setText("Dangerzone is starting up…")

    def handle_shutdown_begin(self) -> None:
        self.label.setText("Dangerzone is shutting down…")

    def handle_task_machine_init(self) -> None:
        self.label.setText(
            "Initializing the Dangerzone VM<br>This might take a few minutes…"
        )

    def handle_task_machine_start(self) -> None:
        self.label.setText("Starting the Dangerzone VM…")

    def handle_task_machine_stop_others(self) -> None:
        self.label.setText("Stopping other Podman VMs…")

    def handle_task_update_check(self) -> None:
        self.label.setText("Checking for updates…")

    def handle_task_container_install(self) -> None:
        self.label.setText(
            "Installing the Dangerzone sandbox<br>This might take a few minutes…"
        )

    def handle_task_container_stop(self) -> None:
        self.label.setText("Stopping the Dangerzone sandbox…")

    def handle_task_machine_init_failed(self, error: str) -> None:
        self.label.setText("Initializing the Dangerzone VM… failed")

    def handle_task_machine_start_failed(self, error: str) -> None:
        self.label.setText("Starting the Dangerzone VM… failed")

    def handle_task_machine_stop_others_failed(self, error: str) -> None:
        self.label.setText("Stopping other Podman VMs… failed")

    def handle_task_machine_stop(self) -> None:
        self.label.setText("Stopping Dangerzone VM…")

    def handle_task_update_check_failed(self, error: str) -> None:
        self.label.setText("Checking for updates… failed")

    def handle_task_container_install_failed(self, error: str) -> None:
        self.label.setText("Installing the Dangerzone sandbox… failed")

    def handle_startup_success(self) -> None:
        self.label.setText("Dangerzone is ready")

    def append_log(self, line: str) -> None:
        self.traceback_widget.process_output(line)
