import shutil
import shlex
import subprocess
from PyQt5 import QtCore, QtGui, QtWidgets

from .tasks import PullImageTask, BuildContainerTask, ConvertToPixels, ConvertToPDF


class TasksWidget(QtWidgets.QWidget):
    def __init__(self, common):
        super(TasksWidget, self).__init__()
        self.common = common

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setStyleSheet("QLabel { font-weight: bold; font-size: 20px; }")

        self.task_details = QtWidgets.QLabel()
        self.task_details.setStyleSheet(
            "QLabel { background-color: #ffffff; font-size: 12px; padding: 10px; }"
        )
        self.task_details.setFont(self.common.fixed_font)
        self.task_details.setAlignment(QtCore.Qt.AlignTop)

        self.details_scrollarea = QtWidgets.QScrollArea()
        self.details_scrollarea.setWidgetResizable(True)
        self.details_scrollarea.setWidget(self.task_details)
        self.details_scrollarea.verticalScrollBar().rangeChanged.connect(
            self.scroll_to_bottom
        )

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.task_label)
        layout.addWidget(self.details_scrollarea)
        self.setLayout(layout)

        self.tasks = []

    def start(self):
        if self.common.settings.get("update_container"):
            self.tasks += [PullImageTask, BuildContainerTask]
        self.tasks += [ConvertToPixels, ConvertToPDF]
        self.next_task()

    def next_task(self):
        if len(self.tasks) == 0:
            self.all_done()
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

    def all_done(self):
        # Save safe PDF
        if self.common.settings.get("save"):
            source_filename = f"{self.common.safe_dir.name}/safe-output-compressed.pdf"
            dest_filename = self.common.save_filename
            shutil.move(source_filename, dest_filename)

        # Open
        if self.common.settings.get("open"):
            if self.common.settings.get("open_app") in self.common.pdf_viewers:
                # Get the PDF reader command
                args = shlex.split(
                    self.common.pdf_viewers[self.common.settings.get("open_app")]
                )
                # %f, %F, %u, and %U are filenames or URLS -- so replace with the file to open
                for i in range(len(args)):
                    if (
                        args[i] == "%f"
                        or args[i] == "%F"
                        or args[i] == "%u"
                        or args[i] == "%U"
                    ):
                        args[i] = self.common.save_filename

                # Open as a background process
                subprocess.Popen(args)

        # Clean up
        self.common.pixel_dir.cleanup()
        self.common.safe_dir.cleanup()

        # Quit
        self.common.app.quit()

    def scroll_to_bottom(self, minimum, maximum):
        self.details_scrollarea.verticalScrollBar().setValue(maximum)
