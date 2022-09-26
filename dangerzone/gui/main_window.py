import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from typing import Optional

from colorama import Fore, Style
from PySide2 import QtCore, QtGui, QtWidgets

from .. import container
from ..container import convert
from ..document import Document
from ..util import get_resource_path, get_subprocess_startupinfo
from .logic import DangerzoneGui

log = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    delete_window = QtCore.Signal(str)

    def __init__(
        self,
        dangerzone: DangerzoneGui,
        window_id: str,
        document: Document,
    ) -> None:
        super(MainWindow, self).__init__()
        self.dangerzone = dangerzone
        self.window_id = window_id
        self.document = document

        self.setWindowTitle("Dangerzone")
        self.setWindowIcon(self.dangerzone.get_window_icon())

        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Header
        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(QtGui.QImage(get_resource_path("icon.png")))
        )
        header_label = QtWidgets.QLabel("dangerzone")
        header_label.setFont(self.dangerzone.fixed_font)
        header_label.setStyleSheet("QLabel { font-weight: bold; font-size: 50px; }")
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        # Waiting widget, replaces content widget while container runtime isn't available
        self.waiting_widget = WaitingWidget(self.dangerzone)
        self.waiting_widget.finished.connect(self.waiting_finished)

        # Content widget, contains all the window content except waiting widget
        self.content_widget = ContentWidget(self.dangerzone, self.document)
        self.content_widget.close_window.connect(self.close)

        # Only use the waiting widget if container runtime isn't available
        if self.dangerzone.is_waiting_finished:
            self.waiting_widget.hide()
            self.content_widget.show()
        else:
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

    def waiting_finished(self) -> None:
        self.dangerzone.is_waiting_finished = True
        self.waiting_widget.hide()
        self.content_widget.show()

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        e.accept()
        self.delete_window.emit(self.window_id)

        if platform.system() != "Darwin":
            self.dangerzone.app.quit()


class InstallContainerThread(QtCore.QThread):
    finished = QtCore.Signal()

    def __init__(self) -> None:
        super(InstallContainerThread, self).__init__()

    def run(self) -> None:
        container.install()
        self.finished.emit()


class WaitingWidget(QtWidgets.QWidget):
    # These are the possible states that the WaitingWidget can show.
    #
    # Windows and macOS states:
    # - "not_installed"
    # - "not_running"
    # - "install_container"
    #
    # Linux states
    # - "install_container"
    finished = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(WaitingWidget, self).__init__()
        self.dangerzone = dangerzone

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setOpenExternalLinks(True)
        self.label.setStyleSheet("QLabel { font-size: 20px; }")

        # Buttons
        check_button = QtWidgets.QPushButton("Check Again")
        check_button.clicked.connect(self.check_state)
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(check_button)
        buttons_layout.addStretch()
        self.buttons = QtWidgets.QWidget()
        self.buttons.setLayout(buttons_layout)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.buttons)
        layout.addStretch()
        self.setLayout(layout)

        # Check the state
        self.check_state()

    def check_state(self) -> None:
        state: Optional[str] = None

        try:
            container_runtime = container.get_runtime()
        except container.NoContainerTechException as e:
            log.error(str(e))
            state = "not_installed"

        else:
            # Can we run `docker image ls` without an error
            with subprocess.Popen(
                [container_runtime, "image", "ls"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=get_subprocess_startupinfo(),
            ) as p:
                p.communicate()
                if p.returncode != 0:
                    log.error("Docker is not running")
                    state = "not_running"
                else:
                    # Always try installing the container
                    state = "install_container"

        # Update the state
        self.state_change(state)

    def state_change(self, state: str) -> None:
        if state == "not_installed":
            self.label.setText(
                "<strong>Dangerzone Requires Docker Desktop</strong><br><br><a href='https://www.docker.com/products/docker-desktop'>Download Docker Desktop</a>, install it, and open it."
            )
            self.buttons.show()
        elif state == "not_running":
            self.label.setText(
                "<strong>Dangerzone Requires Docker Desktop</strong><br><br>Docker is installed but isn't running.<br><br>Open Docker and make sure it's running in the background."
            )
            self.buttons.show()
        else:
            self.label.setText(
                "Installing the Dangerzone container image.<br><br>This might take a few minutes..."
            )
            self.buttons.hide()
            self.install_container_t = InstallContainerThread()
            self.install_container_t.finished.connect(self.finished)
            self.install_container_t.start()


class ContentWidget(QtWidgets.QWidget):
    close_window = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui, document: Document) -> None:
        super(ContentWidget, self).__init__()

        self.dangerzone = dangerzone
        self.document = document

        # Doc selection widget
        self.doc_selection_widget = DocSelectionWidget(self.document)
        self.doc_selection_widget.document_selected.connect(self.document_selected)

        # Settings
        self.settings_widget = SettingsWidget(self.dangerzone, self.document)
        self.doc_selection_widget.document_selected.connect(
            self.settings_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.close_window.connect(self._close_window)
        self.settings_widget.hide()

        # Convert
        self.convert_widget = ConvertWidget(self.dangerzone, self.document)
        self.convert_widget.close_window.connect(self._close_window)
        self.doc_selection_widget.document_selected.connect(
            self.convert_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.convert_widget.start)
        self.convert_widget.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.doc_selection_widget, stretch=1)
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.convert_widget, stretch=1)
        self.setLayout(layout)

    def document_selected(self) -> None:
        self.doc_selection_widget.hide()
        self.settings_widget.show()

    def start_clicked(self) -> None:
        self.settings_widget.hide()
        self.convert_widget.show()

    def _close_window(self) -> None:
        self.close_window.emit()


class DocSelectionWidget(QtWidgets.QWidget):
    document_selected = QtCore.Signal()

    def __init__(self, document: Document) -> None:
        super(DocSelectionWidget, self).__init__()
        self.document = document

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

    def dangerous_doc_button_clicked(self) -> None:
        (filename, _) = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open document",
            filter="Documents (*.pdf *.docx *.doc *.docm *.xlsx *.xls *.pptx *.ppt *.odt *.odg *.odp *.ods *.jpg *.jpeg *.gif *.png *.tif *.tiff)",
        )
        if filename != "":
            self.document.input_filename = filename
            self.document_selected.emit()


class SettingsWidget(QtWidgets.QWidget):
    start_clicked = QtCore.Signal()
    close_window = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui, document: Document) -> None:
        super(SettingsWidget, self).__init__()
        self.dangerzone = dangerzone
        self.document = document

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
            for k in self.dangerzone.pdf_viewers:
                self.open_combobox.addItem(k, self.dangerzone.pdf_viewers[k])

        if platform.system() == "Darwin" or platform.system() == "Linux":
            open_layout = QtWidgets.QHBoxLayout()
            open_layout.addWidget(self.open_checkbox)
            if platform.system() == "Linux":
                open_layout.addWidget(self.open_combobox)
            open_layout.addStretch()

        # OCR document
        self.ocr_checkbox = QtWidgets.QCheckBox("OCR document, language")
        self.ocr_combobox = QtWidgets.QComboBox()
        for k in self.dangerzone.ocr_languages:
            self.ocr_combobox.addItem(k, self.dangerzone.ocr_languages[k])
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
        if self.dangerzone.settings.get("save"):
            self.save_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.save_checkbox.setCheckState(QtCore.Qt.Unchecked)

        if self.dangerzone.settings.get("ocr"):
            self.ocr_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.ocr_checkbox.setCheckState(QtCore.Qt.Unchecked)

        index = self.ocr_combobox.findText(self.dangerzone.settings.get("ocr_language"))
        if index != -1:
            self.ocr_combobox.setCurrentIndex(index)

        if platform.system() == "Darwin" or platform.system() == "Linux":
            if self.dangerzone.settings.get("open"):
                self.open_checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.open_checkbox.setCheckState(QtCore.Qt.Unchecked)

            if platform.system() == "Linux":
                index = self.open_combobox.findText(
                    self.dangerzone.settings.get("open_app")
                )
                if index != -1:
                    self.open_combobox.setCurrentIndex(index)

    def update_ui(self) -> None:
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

    def document_selected(self) -> None:
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Suspicious: {os.path.basename(self.document.input_filename)}"
        )
        self.save_lineedit.setText(os.path.basename(self.document.output_filename))

    def save_browse_button_clicked(self) -> None:
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save safe PDF as...",
            self.document.output_filename,
            filter="Documents (*.pdf)",
        )
        if filename[0] != "":
            self.document.output_filename = filename[0]
            self.save_lineedit.setText(os.path.basename(self.document.output_filename))

    def start_button_clicked(self) -> None:
        if self.save_checkbox.checkState() == QtCore.Qt.Unchecked:
            # If not saving, then save it to a temp file instead
            tmp = tempfile.mkstemp(suffix=".pdf", prefix="dangerzone_")
            self.document.output_filename = tmp[1]

        # Update settings
        self.dangerzone.settings.set(
            "save", self.save_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.dangerzone.settings.set(
            "ocr", self.ocr_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.dangerzone.settings.set("ocr_language", self.ocr_combobox.currentText())
        if platform.system() == "Darwin" or platform.system() == "Linux":
            self.dangerzone.settings.set(
                "open", self.open_checkbox.checkState() == QtCore.Qt.Checked
            )
            if platform.system() == "Linux":
                self.dangerzone.settings.set(
                    "open_app", self.open_combobox.currentText()
                )
        self.dangerzone.settings.save()

        # Start!
        self.start_clicked.emit()


class ConvertThread(QtCore.QThread):
    finished = QtCore.Signal(bool)
    update = QtCore.Signal(bool, str, int)

    def __init__(self, dangerzone: DangerzoneGui, document: Document) -> None:
        super(ConvertThread, self).__init__()
        self.dangerzone = dangerzone
        self.document = document
        self.error = False

    def run(self) -> None:
        if self.dangerzone.settings.get("ocr"):
            ocr_lang = self.dangerzone.ocr_languages[
                self.dangerzone.settings.get("ocr_language")
            ]
        else:
            ocr_lang = None

        if convert(
            self.document,
            ocr_lang,
            self.stdout_callback,
        ):
            self.finished.emit(self.error)

    def stdout_callback(self, error: bool, text: str, percentage: int) -> None:
        if error:
            self.error = True

        self.update.emit(error, text, percentage)


class ConvertWidget(QtWidgets.QWidget):
    close_window = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui, document: Document) -> None:
        super(ConvertWidget, self).__init__()
        self.dangerzone = dangerzone
        self.document = document

        self.error = False

        # Dangerous document label
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dangerous_doc_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: bold; }"
        )

        # Label
        self.error_image = QtWidgets.QLabel()
        self.error_image.setPixmap(
            QtGui.QPixmap.fromImage(QtGui.QImage(get_resource_path("error.png")))
        )
        self.error_image.hide()

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("QLabel { font-size: 18px; }")

        label_layout = QtWidgets.QHBoxLayout()
        label_layout.addWidget(self.error_image)
        label_layout.addWidget(self.label, stretch=1)

        # Progress bar
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.dangerous_doc_label)
        layout.addStretch()
        layout.addLayout(label_layout)
        layout.addWidget(self.progress)
        layout.addStretch()
        self.setLayout(layout)

    def document_selected(self) -> None:
        # Update the danger doc label
        self.dangerous_doc_label.setText(
            f"Suspicious: {os.path.basename(self.document.input_filename)}"
        )

    def start(self) -> None:
        self.convert_t = ConvertThread(self.dangerzone, self.document)
        self.convert_t.update.connect(self.update_progress)
        self.convert_t.finished.connect(self.all_done)
        self.convert_t.start()

    def update_progress(self, error: bool, text: str, percentage: int) -> None:
        if error:
            self.error = True
            self.error_image.show()
            self.progress.hide()

        self.label.setText(text)
        self.progress.setValue(percentage)

    def all_done(self) -> None:
        if self.error:
            return

        # In Windows, open Explorer with the safe PDF in focus
        if platform.system() == "Windows":
            dest_filename_windows = self.document.output_filename.replace("/", "\\")
            subprocess.Popen(
                f'explorer.exe /select,"{dest_filename_windows}"',
                shell=True,
                startupinfo=get_subprocess_startupinfo(),
            )

        # Open
        if self.dangerzone.settings.get("open"):
            self.dangerzone.open_pdf_viewer(self.document.output_filename)

        # Quit
        if platform.system() == "Darwin":
            # In macOS, just close the window
            self.close_window.emit()
        else:
            self.dangerzone.app.quit()
