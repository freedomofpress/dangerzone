import shutil
import tempfile
import os
import platform
import subprocess
from PySide2 import QtCore, QtGui, QtWidgets

from ..tasks import PullImageTask, ConvertToPixels, ConvertToPDF


class TasksWidget(QtWidgets.QWidget):
    close_window = QtCore.Signal()

    def __init__(self, global_common, gui_common, common):
        super(TasksWidget, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.common = common

        # Dangerous document label
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dangerous_doc_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: bold; color: #572606; }"
        )

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setStyleSheet("QLabel { font-weight: bold; font-size: 20px; }")

        self.task_details = QtWidgets.QLabel()
        self.task_details.setStyleSheet(
            "QLabel { background-color: #ffffff; font-size: 12px; padding: 10px; }"
        )
        self.task_details.setFont(self.gui_common.fixed_font)
        self.task_details.setAlignment(QtCore.Qt.AlignTop)

        self.details_scrollarea = QtWidgets.QScrollArea()
        self.details_scrollarea.setWidgetResizable(True)
        self.details_scrollarea.setWidget(self.task_details)
        self.details_scrollarea.verticalScrollBar().rangeChanged.connect(
            self.scroll_to_bottom
        )

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.dangerous_doc_label)
        layout.addSpacing(20)
        layout.addWidget(self.task_label)
        layout.addWidget(self.details_scrollarea)
        self.setLayout(layout)

        self.tasks = []

    def document_selected(self):
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Dangerous: {os.path.basename(self.common.document_filename)}"
        )

    def start(self):
        if self.global_common.settings.get("update_container"):
            self.tasks += [PullImageTask]
        self.tasks += [ConvertToPixels, ConvertToPDF]
        self.next_task()

    def next_task(self):
        if len(self.tasks) == 0:
            self.all_done()
            return

        self.task_details.setText("")

        self.current_task = self.tasks.pop(0)(self.global_common, self.common)
        self.current_task.update_label.connect(self.update_label)
        self.current_task.update_details.connect(self.update_details)
        self.current_task.task_finished.connect(self.next_task)
        self.current_task.task_failed.connect(self.task_failed)
        self.current_task.start()

    def update_label(self, s):
        self.task_label.setText(s)

    def update_details(self, s):
        self.task_details.setText(s)

    def task_failed(self, err):
        self.task_label.setText("Failed :(")
        self.task_details.setWordWrap(True)
        text = self.task_details.text()
        self.task_details.setText(
            f"{text}\n\n--\n\nDirectory with pixel data: {self.common.pixel_dir.name}\n\n{err}"
        )

    def all_done(self):
        # Save safe PDF
        source_filename = f"{self.common.safe_dir.name}/safe-output-compressed.pdf"
        if self.global_common.settings.get("save"):
            dest_filename = self.common.save_filename
        else:
            # If not saving, then save it to a temp file instead
            tmp = tempfile.mkstemp(suffix=".pdf", prefix="dangerzone_")
            dest_filename = tmp[1]
        shutil.move(source_filename, dest_filename)

        # In Windows, open Explorer with the safe PDF in focus
        if platform.system() == "Windows":
            dest_filename_windows = dest_filename.replace("/", "\\")
            subprocess.Popen(
                f'explorer.exe /select,"{dest_filename_windows}"', shell=True
            )

        # Open
        if self.global_common.settings.get("open"):
            self.gui_common.open_pdf_viewer(dest_filename)

        # Clean up
        self.common.pixel_dir.cleanup()
        self.common.safe_dir.cleanup()

        # Quit
        if platform.system() == "Darwin":
            # In macOS, just close the window
            self.close_window.emit()
        else:
            self.gui_common.app.quit()

    def scroll_to_bottom(self, minimum, maximum):
        self.details_scrollarea.verticalScrollBar().setValue(maximum)
