import os
import platform
import tempfile
import subprocess
from PySide2 import QtCore, QtGui, QtWidgets

from .tasks import Convert
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

        # Waiting widget, replaces content widget while VM is booting
        self.waiting_widget = WaitingWidget(self.global_common, self.gui_common)
        self.waiting_widget.finished.connect(self.waiting_finished)

        # Content widget, contains all the window content except waiting widget
        self.content_widget = ContentWidget(
            self.global_common, self.gui_common, self.common
        )
        self.content_widget.close_window.connect(self.close)

        # Only use the waiting widget if we have a VM
        self.waiting_widget.show()
        self.content_widget.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addWidget(self.waiting_widget, stretch=1)
        layout.addWidget(self.content_widget, stretch=1)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.show()

    def waiting_finished(self):
        self.waiting_widget.hide()
        self.content_widget.show()

    def closeEvent(self, e):
        e.accept()
        self.delete_window.emit(self.window_id)

        if platform.system() != "Darwin":
            self.gui_common.app.quit()


class InstallContainerThread(QtCore.QThread):
    finished = QtCore.Signal()

    def __init__(self, global_common):
        super(InstallContainerThread, self).__init__()
        self.global_common = global_common

    def run(self):
        if not self.global_common.is_container_installed():
            self.global_common.install_container()

        self.finished.emit()


class WaitingWidget(QtWidgets.QWidget):
    finished = QtCore.Signal()

    def __init__(self, global_common, gui_common):
        super(WaitingWidget, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("QLabel { font-size: 20px; }")

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addStretch()
        self.setLayout(layout)

        if platform.system() == "Darwin":
            self.label.setText("Waiting for the Dangerzone virtual machine to start...")
            self.global_common.vm.vm_state_change.connect(self.vm_state_change)

        elif platform.system() == "Linux":
            self.label.setText("Installing the Dangerzone container...")
            self.install_container_t = InstallContainerThread(self.global_common)
            self.install_container_t.finished.connect(self.finished)
            self.install_container_t.start()

        else:
            self.label.setText("Platform not implemented yet")

    def vm_state_change(self, state):
        if state == self.global_common.vm.STATE_ON:
            self.finished.emit()
        elif state == self.global_common.vm.STATE_FAIL:
            self.label.setText("Dangerzone virtual machine failed to start :(")


class ContentWidget(QtWidgets.QWidget):
    close_window = QtCore.Signal()

    def __init__(self, global_common, gui_common, common):
        super(ContentWidget, self).__init__()

        self.global_common = global_common
        self.gui_common = gui_common
        self.common = common

        # Doc selection widget
        self.doc_selection_widget = DocSelectionWidget(self.common)
        self.doc_selection_widget.document_selected.connect(self.document_selected)

        # Settings
        self.settings_widget = SettingsWidget(
            self.global_common, self.gui_common, self.common
        )
        self.doc_selection_widget.document_selected.connect(
            self.settings_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.close_window.connect(self._close_window)
        self.settings_widget.hide()

        # Tasks
        self.tasks_widget = TasksWidget(
            self.global_common, self.gui_common, self.common
        )
        self.tasks_widget.close_window.connect(self._close_window)
        self.doc_selection_widget.document_selected.connect(
            self.tasks_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.tasks_widget.start)
        self.tasks_widget.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.doc_selection_widget, stretch=1)
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.tasks_widget, stretch=1)
        self.setLayout(layout)

    def document_selected(self):
        self.doc_selection_widget.hide()
        self.settings_widget.show()

    def start_clicked(self):
        self.settings_widget.hide()
        self.tasks_widget.show()

    def _close_window(self):
        self.close_window.emit()


class DocSelectionWidget(QtWidgets.QWidget):
    document_selected = QtCore.Signal()

    def __init__(self, common):
        super(DocSelectionWidget, self).__init__()
        self.common = common

        # Dangerous document selection
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.hide()
        self.dangerous_doc_button = QtWidgets.QPushButton(
            "Select suspicious document ..."
        )
        self.dangerous_doc_button.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 10px; }"
        )
        self.dangerous_doc_button.clicked.connect(self.dangerous_doc_button_clicked)

        dangerous_doc_layout = QtWidgets.QHBoxLayout()
        dangerous_doc_layout.addStretch()
        dangerous_doc_layout.addWidget(self.dangerous_doc_button)
        dangerous_doc_layout.addStretch()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addLayout(dangerous_doc_layout)
        layout.addStretch()
        self.setLayout(layout)

    def dangerous_doc_button_clicked(self):
        filename = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open document",
            filter="Documents (*.pdf *.docx *.doc *.docm *.xlsx *.xls *.pptx *.ppt *.odt *.odg *.odp *.ods *.jpg *.jpeg *.gif *.png *.tif *.tiff)",
        )
        if filename[0] != "":
            filename = filename[0]
            self.common.input_filename = filename
            self.document_selected.emit()


class SettingsWidget(QtWidgets.QWidget):
    start_clicked = QtCore.Signal()
    close_window = QtCore.Signal()

    def __init__(self, global_common, gui_common, common):
        super(SettingsWidget, self).__init__()
        self.global_common = global_common
        self.gui_common = gui_common
        self.common = common

        # Dangerous document label
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dangerous_doc_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: bold; }"
        )

        # Save safe version
        self.save_checkbox = QtWidgets.QCheckBox("Save safe PDF")
        self.save_checkbox.clicked.connect(self.update_ui)
        self.save_label = QtWidgets.QLabel("Save safe PDF")  # For Windows
        self.save_label.hide()
        if platform.system() == "Windows":
            # In Windows, users must save the PDF, since they can't open it
            self.save_checkbox.setCheckState(QtCore.Qt.Checked)
            self.save_checkbox.setEnabled(False)
            self.save_checkbox.hide()
            self.save_label.show()
        self.save_lineedit = QtWidgets.QLineEdit()
        self.save_lineedit.setReadOnly(True)
        self.save_browse_button = QtWidgets.QPushButton("Save as...")
        self.save_browse_button.clicked.connect(self.save_browse_button_clicked)
        save_layout = QtWidgets.QHBoxLayout()
        save_layout.addWidget(self.save_checkbox)
        save_layout.addWidget(self.save_label)
        save_layout.addWidget(self.save_lineedit)
        save_layout.addWidget(self.save_browse_button)
        save_layout.addStretch()

        # Open safe document
        if platform.system() == "Darwin":
            self.open_checkbox = QtWidgets.QCheckBox(
                "Open safe document after converting"
            )
            self.open_checkbox.clicked.connect(self.update_ui)

        elif platform.system() == "Linux":
            self.open_checkbox = QtWidgets.QCheckBox(
                "Open safe document after converting, using"
            )
            self.open_checkbox.clicked.connect(self.update_ui)
            self.open_combobox = QtWidgets.QComboBox()
            for k in self.gui_common.pdf_viewers:
                self.open_combobox.addItem(k, self.gui_common.pdf_viewers[k])

        if platform.system() == "Darwin" or platform.system() == "Linux":
            open_layout = QtWidgets.QHBoxLayout()
            open_layout.addWidget(self.open_checkbox)
            if platform.system() == "Linux":
                open_layout.addWidget(self.open_combobox)
            open_layout.addStretch()

        # OCR document
        self.ocr_checkbox = QtWidgets.QCheckBox("OCR document, language")
        self.ocr_combobox = QtWidgets.QComboBox()
        for k in self.global_common.ocr_languages:
            self.ocr_combobox.addItem(k, self.global_common.ocr_languages[k])
        ocr_layout = QtWidgets.QHBoxLayout()
        ocr_layout.addWidget(self.ocr_checkbox)
        ocr_layout.addWidget(self.ocr_combobox)
        ocr_layout.addStretch()

        # Button
        self.start_button = QtWidgets.QPushButton("Convert to Safe Document")
        self.start_button.clicked.connect(self.start_button_clicked)
        self.start_button.setStyleSheet(
            "QPushButton { font-size: 16px; font-weight: bold; }"
        )
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.start_button)
        button_layout.addStretch()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.dangerous_doc_label)
        layout.addSpacing(20)
        layout.addLayout(save_layout)
        if platform.system() != "Windows":
            layout.addLayout(open_layout)
        layout.addLayout(ocr_layout)
        layout.addSpacing(20)
        layout.addLayout(button_layout)
        layout.addStretch()
        self.setLayout(layout)

        # Load values from settings
        if self.global_common.settings.get("save"):
            self.save_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.save_checkbox.setCheckState(QtCore.Qt.Unchecked)

        if self.global_common.settings.get("ocr"):
            self.ocr_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.ocr_checkbox.setCheckState(QtCore.Qt.Unchecked)

        index = self.ocr_combobox.findText(
            self.global_common.settings.get("ocr_language")
        )
        if index != -1:
            self.ocr_combobox.setCurrentIndex(index)

        if platform.system() == "Darwin" or platform.system() == "Linux":
            if self.global_common.settings.get("open"):
                self.open_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.open_checkbox.setCheckState(QtCore.Qt.Unchecked)

            if platform.system() == "Linux":
                index = self.open_combobox.findText(
                    self.global_common.settings.get("open_app")
                )
                if index != -1:
                    self.open_combobox.setCurrentIndex(index)

    def update_ui(self):
        if platform.system() == "Windows":
            # Because the save checkbox is always checked in Windows, the
            # start button can be enabled
            self.start_button.setEnabled(True)
        else:
            # Either save or open must be checked
            if (
                self.save_checkbox.checkState() == QtCore.Qt.Checked
                or self.open_checkbox.checkState() == QtCore.Qt.Checked
            ):
                self.start_button.setEnabled(True)
            else:
                self.start_button.setEnabled(False)

    def document_selected(self):
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Suspicious: {os.path.basename(self.common.input_filename)}"
        )

        # Update the save location
        output_filename = f"{os.path.splitext(self.common.input_filename)[0]}-safe.pdf"
        self.common.output_filename = output_filename
        self.save_lineedit.setText(os.path.basename(output_filename))

    def save_browse_button_clicked(self):
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save safe PDF as...",
            self.common.output_filename,
            filter="Documents (*.pdf)",
        )
        if filename[0] != "":
            self.common.output_filename = filename[0]
            self.save_lineedit.setText(os.path.basename(self.common.output_filename))

    def start_button_clicked(self):
        if self.common.output_filename is None:
            # If not saving, then save it to a temp file instead
            tmp = tempfile.mkstemp(suffix=".pdf", prefix="dangerzone_")
            self.common.output_filename = tmp[1]

        # Update settings
        self.global_common.settings.set(
            "save", self.save_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.global_common.settings.set(
            "ocr", self.ocr_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.global_common.settings.set("ocr_language", self.ocr_combobox.currentText())
        if platform.system() == "Darwin" or platform.system() == "Linux":
            self.global_common.settings.set(
                "open", self.open_checkbox.checkState() == QtCore.Qt.Checked
            )
            if platform.system() == "Linux":
                self.global_common.settings.set(
                    "open_app", self.open_combobox.currentText()
                )
        self.global_common.settings.save()

        # Start!
        self.start_clicked.emit()


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
            "QLabel { font-size: 16px; font-weight: bold; }"
        )

        self.task_label = QtWidgets.QLabel()
        self.task_label.setAlignment(QtCore.Qt.AlignCenter)
        self.task_label.setStyleSheet("QLabel { font-weight: bold; font-size: 20px; }")

        self.task_details = QtWidgets.QLabel()
        self.task_details.setStyleSheet("QLabel { font-size: 12px; padding: 10px; }")
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

    def document_selected(self):
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Suspicious: {os.path.basename(self.common.input_filename)}"
        )

    def start(self):
        self.task_details.setText("")

        self.task = Convert(self.global_common, self.common)
        self.task.update_label.connect(self.update_label)
        self.task.update_details.connect(self.update_details)
        self.task.task_finished.connect(self.all_done)
        self.task.task_failed.connect(self.task_failed)
        self.task.start()

    def update_label(self, s):
        self.task_label.setText(s)

    def update_details(self, s):
        self.task_details.setText(s)

    def task_failed(self, err):
        self.task_label.setText("Failed :(")
        self.task_details.setWordWrap(True)

    def all_done(self):
        # In Windows, open Explorer with the safe PDF in focus
        if platform.system() == "Windows":
            dest_filename_windows = self.common.output_filename.replace("/", "\\")
            subprocess.Popen(
                f'explorer.exe /select,"{dest_filename_windows}"', shell=True
            )

        # Open
        if self.global_common.settings.get("open"):
            self.gui_common.open_pdf_viewer(self.common.output_filename)

        # Quit
        if platform.system() == "Darwin":
            # In macOS, just close the window
            self.close_window.emit()
        else:
            self.gui_common.app.quit()

    def scroll_to_bottom(self, minimum, maximum):
        self.details_scrollarea.verticalScrollBar().setValue(maximum)
