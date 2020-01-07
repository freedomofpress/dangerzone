import shutil
import os
from PyQt5 import QtCore, QtGui, QtWidgets

from .tasks import PullImageTask, BuildContainerTask, ConvertToPixels, ConvertToPDF


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app, common):
        super(MainWindow, self).__init__()
        self.app = app
        self.common = common

        self.setWindowTitle("dangerzone")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setStyleSheet("QLabel { font-weight: bold; font-size: 20px; }")

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.task_details = QtWidgets.QLabel()
        self.task_details.setStyleSheet(
            "QLabel { background-color: #ffffff; font-size: 12px; padding: 10px; }"
        )
        self.task_details.setFont(font)
        self.task_details.setAlignment(QtCore.Qt.AlignTop)

        self.details_scrollarea = QtWidgets.QScrollArea()
        self.details_scrollarea.setWidgetResizable(True)
        self.details_scrollarea.setWidget(self.task_details)
        self.details_scrollarea.verticalScrollBar().rangeChanged.connect(
            self.scroll_to_bottom
        )

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.task_label)
        layout.addWidget(self.details_scrollarea, stretch=1)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.tasks = [PullImageTask, BuildContainerTask, ConvertToPixels, ConvertToPDF]

    def start(self, filename):
        print(f"Input document: {filename}")
        self.common.document_filename = filename
        self.show()

        self.next_task()

    def next_task(self):
        if len(self.tasks) == 0:
            self.save_safe_pdf()
            return

        self.task_details.setText("")

        self.current_task = self.tasks.pop(0)(self.common)
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
        self.task_label.setText("Task failed :(")
        self.task_details.setWordWrap(True)
        self.task_details.setText(
            f"Directory with pixel data: {self.common.pixel_dir.name}\n\n{err}"
        )

    def save_safe_pdf(self):
        suggested_filename = (
            f"{os.path.splitext(self.common.document_filename)[0]}-safe.pdf"
        )

        filename = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save safe PDF", suggested_filename, filter="Documents (*.pdf)"
        )
        if filename[0] == "":
            print("Save file dialog canceled")
        else:
            source_filename = f"{self.common.safe_dir.name}/safe-output-compressed.pdf"
            dest_filename = filename[0]
            shutil.move(source_filename, dest_filename)

            # Clean up
            self.common.pixel_dir.cleanup()
            self.common.safe_dir.cleanup()

            # Quit
            self.app.quit()

    def scroll_to_bottom(self, minimum, maximum):
        self.details_scrollarea.verticalScrollBar().setValue(maximum)

    def closeEvent(self, e):
        e.accept()
        self.app.quit()
