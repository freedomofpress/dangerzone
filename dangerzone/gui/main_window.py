import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from typing import List, Optional

from colorama import Fore, Style
from PySide2 import QtCore, QtGui, QtWidgets

from .. import container
from ..container import convert
from ..document import SAFE_EXTENSION, Document
from ..util import get_resource_path, get_subprocess_startupinfo
from .logic import DangerzoneGui

log = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(MainWindow, self).__init__()
        self.dangerzone = dangerzone

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
        self.content_widget = ContentWidget(self.dangerzone)

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

        if platform.system() != "Darwin":
            # in MacOS applications only quit when the user
            # explicitly closes them
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
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(ContentWidget, self).__init__()
        self.dangerzone = dangerzone

        # Doc selection widget
        self.doc_selection_widget = DocSelectionWidget()
        self.doc_selection_widget.document_selected.connect(self.document_selected)

        # Settings
        self.settings_widget = SettingsWidget(self.dangerzone)
        self.doc_selection_widget.document_selected.connect(
            self.settings_widget.document_selected
        )
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.hide()

        # Convert
        self.documents_list = DocumentsListWidget(self.dangerzone)
        self.doc_selection_widget.document_selected.connect(
            self.documents_list.document_selected
        )
        self.settings_widget.start_clicked.connect(self.documents_list.start)
        self.documents_list.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.documents_list, stretch=1)
        layout.addWidget(self.doc_selection_widget, stretch=1)
        self.setLayout(layout)

    def document_selected(self) -> None:
        self.doc_selection_widget.hide()
        self.settings_widget.show()

    def start_clicked(self) -> None:
        self.settings_widget.hide()
        self.documents_list.show()


class DocSelectionWidget(QtWidgets.QWidget):
    document_selected = QtCore.Signal(list)

    def __init__(self) -> None:
        super(DocSelectionWidget, self).__init__()

        # Dangerous document selection
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.hide()
        self.dangerous_doc_button = QtWidgets.QPushButton(
            "Select suspicious documents ..."
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
        (filenames, _) = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Open documents",
            filter="Documents (*.pdf *.docx *.doc *.docm *.xlsx *.xls *.pptx *.ppt *.odt *.odg *.odp *.ods *.jpg *.jpeg *.gif *.png *.tif *.tiff)",
        )
        if filenames == []:
            # no files selected
            return

        self.document_selected.emit(filenames)


class SettingsWidget(QtWidgets.QWidget):
    start_clicked = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(SettingsWidget, self).__init__()
        self.dangerzone = dangerzone

        # Save safe version
        self.save_checkbox = QtWidgets.QCheckBox("Save safe PDF to")
        self.save_checkbox.clicked.connect(self.update_ui)
        self.save_label = QtWidgets.QLabel("Save safe PDF to")  # For Windows
        self.save_label.hide()
        self.output_dir = None
        if platform.system() == "Windows":
            # In Windows, users must save the PDF, since they can't open it
            self.save_checkbox.setCheckState(QtCore.Qt.Checked)
            self.save_checkbox.setEnabled(False)
            self.save_checkbox.hide()
            self.save_label.show()

        # Save safe to...
        self.save_location = QtWidgets.QLineEdit()
        self.save_location.setReadOnly(True)
        self.save_browse_button = QtWidgets.QPushButton("Choose...")
        self.save_browse_button.clicked.connect(self.select_output_directory)
        self.save_location_layout = QtWidgets.QHBoxLayout()
        self.save_location_layout.addWidget(self.save_checkbox)
        self.save_location_layout.addWidget(self.save_location)
        self.save_location_layout.addWidget(self.save_browse_button)
        self.save_location_layout.addStretch()

        # Save safe as... [filename]-safe.pdf
        self.safe_extension_label = QtWidgets.QLabel("Save as")
        self.safe_extension_filename = QtWidgets.QLabel("document")
        self.safe_extension_filename.setAlignment(QtCore.Qt.AlignRight)
        self.safe_extension_filename.setProperty("style", "safe_extension_filename")
        self.safe_extension = QtWidgets.QLineEdit()
        self.safe_extension.setStyleSheet("margin-left: -6px;")  # no left margin
        self.safe_extension.textChanged.connect(self.update_ui)
        self.safe_extension_invalid = QtWidgets.QLabel("(must end in .pdf)")
        self.safe_extension_invalid.setStyleSheet("color: red")
        self.safe_extension_invalid.hide()
        self.safe_extension_name_layout = QtWidgets.QHBoxLayout()
        self.safe_extension_name_layout.setSpacing(0)
        self.safe_extension_name_layout.addWidget(self.safe_extension_filename)
        self.safe_extension_name_layout.addWidget(self.safe_extension)

        dot_pdf_regex = QtCore.QRegExp(r".*\.[Pp][Dd][Ff]")
        self.safe_extension.setValidator(QtGui.QRegExpValidator(dot_pdf_regex))
        self.safe_extension_layout = QtWidgets.QHBoxLayout()
        self.safe_extension_layout.setContentsMargins(20, 0, 0, 0)
        self.safe_extension_layout.addWidget(self.safe_extension_label)
        self.safe_extension_layout.addWidget(self.save_label)
        self.safe_extension_layout.addLayout(self.safe_extension_name_layout)
        self.safe_extension_layout.addWidget(self.safe_extension_invalid)

        self.safe_extension_layout.addStretch()

        # Open safe document
        if platform.system() == "Darwin":
            self.open_checkbox = QtWidgets.QCheckBox(
                "Open safe documents after converting"
            )
            self.open_checkbox.clicked.connect(self.update_ui)

        elif platform.system() == "Linux":
            self.open_checkbox = QtWidgets.QCheckBox(
                "Open safe documents after converting, using"
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
        layout.addSpacing(20)
        layout.addLayout(self.save_location_layout)
        layout.addLayout(self.safe_extension_layout)
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

        if self.dangerzone.settings.get("safe_extension"):
            self.safe_extension.setText(self.dangerzone.settings.get("safe_extension"))
        else:
            self.safe_extension.setText(SAFE_EXTENSION)

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

    def check_safe_extension_is_valid(self) -> bool:
        if self.save_checkbox.checkState() == QtCore.Qt.Unchecked:
            # ignore validity if not saving file
            self.safe_extension_invalid.hide()
            return True

        if self.safe_extension.hasAcceptableInput():
            self.safe_extension_invalid.hide()
            return True
        else:
            # prevent starting conversion until correct
            self.safe_extension_invalid.show()
            return False

    def check_either_save_or_open(self) -> bool:
        return (
            self.save_checkbox.checkState() == QtCore.Qt.Checked
            or self.open_checkbox.checkState() == QtCore.Qt.Checked
        )

    def update_ui(self) -> None:
        conversion_readiness_conditions = [
            self.check_safe_extension_is_valid(),
            self.check_either_save_or_open(),
        ]
        if all(conversion_readiness_conditions):
            self.start_button.setEnabled(True)
        else:
            self.start_button.setDisabled(True)

    def document_selected(self, filenames: List[str]) -> None:
        # set the default save location as the directory for the first document
        save_path = os.path.dirname(filenames[0])
        save_dir = os.path.basename(save_path)
        self.save_location.setText(save_dir)

        self.update_ui()

    def select_output_directory(self) -> None:
        dialog = QtWidgets.QFileDialog()
        dialog.setLabelText(QtWidgets.QFileDialog.Accept, "Select output directory")

        if self.output_dir is None:
            # pick the first document's directory as the default one
            unconverted_docs = self.dangerzone.get_unconverted_documents()
            if len(unconverted_docs) >= 1:
                dialog.setDirectory(os.path.dirname(unconverted_docs[0].input_filename))
        else:
            # open the directory where the user last saved it
            dialog.setDirectory(self.output_dir)

        # allow only the selection of directories
        dialog.setFileMode(QtWidgets.QFileDialog.DirectoryOnly)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)

        if dialog.exec_() == QtWidgets.QFileDialog.Accepted:
            selected_dir = dialog.selectedFiles()[0]
            if selected_dir is not None:
                self.output_dir = str(selected_dir)  # type: ignore [assignment]
                self.save_location.setText(selected_dir)

    def start_button_clicked(self) -> None:
        if self.save_checkbox.checkState() == QtCore.Qt.Unchecked:
            # If not saving, then save it to a temp file instead
            for document in self.dangerzone.get_unconverted_documents():
                (_, tmp) = tempfile.mkstemp(suffix=".pdf", prefix="dangerzone_")
                document.output_filename = tmp
        else:
            for document in self.dangerzone.get_unconverted_documents():
                document.suffix = self.safe_extension.text()

                if self.output_dir:
                    document.set_output_dir(self.output_dir)  # type: ignore [unreachable]

        # Update settings
        self.dangerzone.settings.set(
            "save", self.save_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.dangerzone.settings.set("safe_extension", self.safe_extension.text())
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


class DocumentsListWidget(QtWidgets.QListWidget):
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super().__init__()
        self.dangerzone = dangerzone
        self.document_widgets: List[DocumentWidget] = []

    def document_selected(self, filenames: list) -> None:
        for filename in filenames:
            self.dangerzone.add_document(filename)

        for document in self.dangerzone.get_unconverted_documents():
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(500, 50))
            widget = DocumentWidget(self.dangerzone, document)
            self.addItem(item)
            self.setItemWidget(item, widget)
            self.document_widgets.append(widget)

    def start(self) -> None:
        for item in self.document_widgets:
            item.start()


class DocumentWidget(QtWidgets.QWidget):
    def __init__(
        self,
        dangerzone: DangerzoneGui,
        document: Document,
    ) -> None:
        super().__init__()
        self.dangerzone = dangerzone
        self.document = document

        self.error = False

        # Dangerous document label
        self.dangerous_doc_label = QtWidgets.QLabel()
        self.dangerous_doc_label.setAlignment(QtCore.Qt.AlignCenter)
        self.dangerous_doc_label.setStyleSheet(
            "QLabel { font-size: 16px; font-weight: bold; }"
        )
        self.dangerous_doc_label.setText(
            f"Suspicious: {os.path.basename(self.document.input_filename)}"
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
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.dangerous_doc_label)
        layout.addStretch()
        layout.addLayout(label_layout)
        layout.addWidget(self.progress)
        layout.addStretch()
        self.setLayout(layout)

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
