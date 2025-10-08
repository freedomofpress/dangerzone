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
        self.setWindowTitle("Dangerzone Logs")
        self.setMinimumSize(600, 400)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setOpenExternalLinks(True)
        self.label.setWordWrap(True)

        self.traceback_widget = TracebackWidget()
        self.traceback_widget.setVisible(True)  # Always visible in the log window

        self.copy_button = QtWidgets.QPushButton("Copy to clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)

        self.copied_label = QtWidgets.QLabel("")

        self.bottom_layout = QtWidgets.QHBoxLayout()
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.copy_button)
        self.bottom_layout.addWidget(self.copied_label)
        self.bottom_layout.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.traceback_widget)
        layout.addLayout(self.bottom_layout)
        self.setLayout(layout)

    def handle_startup_begin(self) -> None:
        self.label.setText("Dangerzone is starting up…")

    def handle_shutdown_begin(self) -> None:
        self.label.setText("Dangerzone is shutting down…")

    def handle_task_machine_init(self) -> None:
        self.label.setText(
            "Initializing Dangerzone sandbox (creating VM)<br>This might take a few minutes…"
        )

    def handle_task_machine_start(self) -> None:
        self.label.setText("Initializing Dangerzone sandbox (starting VM)…")

    def handle_task_machine_stop_others(self) -> None:
        self.label.setText("Initializing Dangerzone sandbox (stopping other VMs)…")

    def handle_task_update_check(self) -> None:
        self.label.setText("Checking for updates…")

    def handle_task_container_install_local(self) -> None:
        self.label.setText(
            "Installing Dangerzone sandbox (from local archive)<br>"
            "This might take a few minutes…"
        )

    def handle_task_container_install_remote(self) -> None:
        self.label.setText(
            "Downloading Dangerzone sandbox (from trusted remote)<br>"
            "This might take a few minutes…"
        )

    def handle_task_container_stop(self) -> None:
        self.label.setText("Stopping the Dangerzone sandbox (clearing jobs)…")

    def handle_task_machine_init_failed(self, error: str) -> None:
        self.label.setText("Initializing Dangerzone sandbox (creating VM)… failed")

    def handle_task_machine_start_failed(self, error: str) -> None:
        self.label.setText("Initializing Dangerzone sandbox (starting VM)… failed")

    def handle_task_machine_stop_others_failed(self, error: str) -> None:
        self.label.setText(
            "Initializing Dangerzone sandbox (stopping other VMs)… failed"
        )

    def handle_task_machine_stop(self) -> None:
        self.label.setText("Stopping Dangerzone sandbox (shutting down VM)…")

    def handle_task_update_check_failed(self, error: str) -> None:
        self.label.setText("Checking for updates… failed")

    def handle_task_container_install_failed(self, error: str) -> None:
        self.label.setText("Installing Dangerzone sandbox… failed")

    def handle_startup_success(self) -> None:
        # We want to hide the text if there's nothing of importance to say to the user,
        # in the same way that we hide the status bar.
        self.label.setText("")

    def append_log(self, line: str) -> None:
        self.traceback_widget.process_output(line)

    def copy_to_clipboard(self) -> None:
        self.traceback_widget.copy_to_clipboard()
        self.copied_label.setText("✓")
        QtCore.QTimer.singleShot(3000, lambda: self.copied_label.setText(""))
