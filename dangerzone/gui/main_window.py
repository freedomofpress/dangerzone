import shutil
import os
import platform
from PySide2 import QtCore, QtGui, QtWidgets

from .doc_selection_widget import DocSelectionWidget
from .settings_widget import SettingsWidget
from .tasks_widget import TasksWidget
from ..common import Common


class MainWindow(QtWidgets.QMainWindow):
    delete_window = QtCore.Signal(str)

    def __init__(self, global_common, gui_common, window_id):
        super(MainWindow, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.window_id = window_id
        self.common = Common()

        self.setWindowTitle("dangerzone")
        self.setWindowIcon(self.gui_common.get_window_icon())

        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Header
        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(
                QtGui.QImage(self.global_common.get_resource_path("icon.png"))
            )
        )
        header_label = QtWidgets.QLabel("dangerzone")
        header_label.setFont(self.gui_common.fixed_font)
        header_label.setStyleSheet("QLabel { font-weight: bold; font-size: 50px; }")
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        # Doc selection widget
        self.doc_selection_widget = DocSelectionWidget(self.common)
        self.doc_selection_widget.document_selected.connect(self.document_selected)
        self.doc_selection_widget.show()

        # Settings
        self.settings_widget = SettingsWidget(
            self.global_common, self.gui_common, self.common
        )
        self.doc_selection_widget.document_selected.connect(
            self.settings_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.close_window.connect(self.close)
        self.settings_widget.hide()
        QtCore.QTimer.singleShot(
            1, self.settings_widget.check_update_container_default_state
        )

        # Tasks
        self.tasks_widget = TasksWidget(
            self.global_common, self.gui_common, self.common
        )
        self.tasks_widget.close_window.connect(self.close)
        self.doc_selection_widget.document_selected.connect(
            self.tasks_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.tasks_widget.start)
        self.tasks_widget.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addWidget(self.doc_selection_widget, stretch=1)
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.tasks_widget, stretch=1)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.show()

    def document_selected(self):
        self.doc_selection_widget.hide()
        self.settings_widget.show()

    def start_clicked(self):
        self.settings_widget.hide()
        self.tasks_widget.show()

    def closeEvent(self, e):
        e.accept()
        self.delete_window.emit(self.window_id)

        if platform.system() != "Darwin":
            self.gui_common.app.quit()
