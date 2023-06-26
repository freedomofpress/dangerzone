import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import typing
from multiprocessing.pool import ThreadPool
from typing import List, Optional

from colorama import Fore, Style

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

from .. import errors
from ..document import SAFE_EXTENSION, Document
from ..isolation_provider.container import Container, NoContainerTechException
from ..isolation_provider.dummy import Dummy
from ..isolation_provider.qubes import Qubes
from ..util import get_resource_path, get_subprocess_startupinfo, get_version
from .logic import Alert, DangerzoneGui

log = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(MainWindow, self).__init__()
        self.dangerzone = dangerzone

        self.setWindowTitle("Dangerzone")
        self.setWindowIcon(self.dangerzone.get_window_icon())

        self.setMinimumWidth(600)
        if platform.system() == "Darwin":
            # FIXME have a different height for macOS due to font-size inconsistencies
            # https://github.com/freedomofpress/dangerzone/issues/270
            self.setMinimumHeight(470)
        else:
            self.setMinimumHeight(430)

        # Header
        logo = QtWidgets.QLabel()
        logo.setPixmap(
            QtGui.QPixmap.fromImage(QtGui.QImage(get_resource_path("icon.png")))
        )
        header_label = QtWidgets.QLabel("dangerzone")
        header_label.setFont(self.dangerzone.fixed_font)
        header_label.setStyleSheet("QLabel { font-weight: bold; font-size: 50px; }")
        header_version_label = QtWidgets.QLabel(get_version())
        header_version_label.setProperty("class", "version")
        header_version_label.setAlignment(QtCore.Qt.AlignBottom)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(header_label)
        header_layout.addWidget(header_version_label)
        header_layout.addStretch()

        if isinstance(self.dangerzone.isolation_provider, Container):
            # Waiting widget replaces content widget while container runtime isn't available
            self.waiting_widget: WaitingWidget = WaitingWidgetContainer(self.dangerzone)
            self.waiting_widget.finished.connect(self.waiting_finished)

        elif isinstance(self.dangerzone.isolation_provider, Dummy) or isinstance(
            self.dangerzone.isolation_provider, Qubes
        ):
            # Don't wait with dummy converter and on Qubes.
            self.waiting_widget = WaitingWidget()
            self.dangerzone.is_waiting_finished = True

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
        alert_widget = Alert(
            self.dangerzone,
            message="Some documents are still being converted.\n Are you sure you want to quit?",
            ok_text="Abort conversions",
        )
        converting_docs = self.dangerzone.get_converting_documents()
        failed_docs = self.dangerzone.get_failed_documents()
        if not converting_docs:
            e.accept()
            if failed_docs:
                self.dangerzone.app.exit(1)
            else:
                self.dangerzone.app.exit(0)
        else:
            accept_exit = alert_widget.exec_()
            if not accept_exit:
                e.ignore()
                return
            else:
                e.accept()

        self.dangerzone.app.exit(2)


class InstallContainerThread(QtCore.QThread):
    finished = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(InstallContainerThread, self).__init__()
        self.dangerzone = dangerzone

    def run(self) -> None:
        self.dangerzone.isolation_provider.install()
        self.finished.emit()


class WaitingWidget(QtWidgets.QWidget):
    finished = QtCore.Signal()

    def __init__(self) -> None:
        super(WaitingWidget, self).__init__()


class WaitingWidgetContainer(WaitingWidget):
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
        super(WaitingWidgetContainer, self).__init__()
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
            if isinstance(  # Sanity check
                self.dangerzone.isolation_provider, Container
            ):
                container_runtime = self.dangerzone.isolation_provider.get_runtime()
        except NoContainerTechException as e:
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
            self.install_container_t = InstallContainerThread(self.dangerzone)
            self.install_container_t.finished.connect(self.finished)
            self.install_container_t.start()


class ContentWidget(QtWidgets.QWidget):
    documents_added = QtCore.Signal(list)

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(ContentWidget, self).__init__()
        self.dangerzone = dangerzone
        self.conversion_started = False

        # Doc selection widget
        self.doc_selection_widget = DocSelectionWidget()
        self.doc_selection_widget.documents_selected.connect(self.documents_selected)

        # Settings
        self.settings_widget = SettingsWidget(self.dangerzone)
        self.documents_added.connect(self.settings_widget.documents_added)
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.hide()

        # Convert
        self.documents_list = DocumentsListWidget(self.dangerzone)
        self.documents_added.connect(self.documents_list.documents_added)
        self.settings_widget.start_clicked.connect(self.documents_list.start_conversion)
        self.documents_list.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.documents_list, stretch=1)
        layout.addWidget(self.doc_selection_widget, stretch=1)
        self.setLayout(layout)

    def documents_selected(self, new_docs: List[Document]) -> None:
        if not self.conversion_started:
            # assumed all files in batch are in the same directory
            first_doc = new_docs[0]
            output_dir = os.path.dirname(first_doc.input_filename)
            if not self.dangerzone.output_dir:
                self.dangerzone.output_dir = output_dir
            elif self.dangerzone.output_dir != output_dir:
                Alert(
                    self.dangerzone,
                    message="Dangerzone does not support adding documents from multiple locations.\n\n The newly added documents were ignored.",
                    has_cancel=False,
                ).exec_()
                return
            else:
                self.dangerzone.output_dir = output_dir

            for doc in new_docs.copy():
                try:
                    self.dangerzone.add_document(doc)
                except errors.AddedDuplicateDocumentException:
                    new_docs.remove(doc)
                    Alert(
                        self.dangerzone,
                        message=f"Document '{doc.input_filename}' has already been added for conversion.",
                        has_cancel=False,
                    ).exec_()

            self.doc_selection_widget.hide()
            self.settings_widget.show()

            if len(new_docs) > 0:
                self.documents_added.emit(new_docs)

        else:
            Alert(
                self.dangerzone,
                message="Dangerzone does not support adding documents after the conversion has started.",
                has_cancel=False,
            ).exec_()

    def start_clicked(self) -> None:
        self.conversion_started = True
        self.settings_widget.hide()
        self.documents_list.show()


class DocSelectionWidget(QtWidgets.QWidget):
    documents_selected = QtCore.Signal(list)

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
            filter="Documents (*.pdf *.docx *.doc *.docm *.xlsx *.xls *.pptx *.ppt *.odt *.odg *.odp *.ods *.hwp *.hwpx *.jpg *.jpeg *.gif *.png *.tif *.tiff)",
        )
        if filenames == []:
            # no files selected
            return

        documents = [Document(filename) for filename in filenames]
        self.documents_selected.emit(documents)


class SettingsWidget(QtWidgets.QWidget):
    start_clicked = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(SettingsWidget, self).__init__()
        self.dangerzone = dangerzone

        # Num Docs Selected
        self.docs_selected_label = QtWidgets.QLabel("No documents selected")
        self.docs_selected_label.setAlignment(QtCore.Qt.AlignCenter)
        self.docs_selected_label.setContentsMargins(0, 0, 0, 20)
        self.docs_selected_label.setProperty("class", "docs-selection")

        # Save safe version
        self.save_checkbox = QtWidgets.QCheckBox()
        self.save_checkbox.clicked.connect(self.update_ui)

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

        # FIXME: Workaround for https://github.com/freedomofpress/dangerzone/issues/339.
        # We should drop this once we drop Ubuntu Focal support.
        if hasattr(QtGui, "QRegularExpressionValidator"):
            dot_pdf_regex = QtCore.QRegularExpression(r".*\.[Pp][Dd][Ff]")
            validator = QtGui.QRegularExpressionValidator(dot_pdf_regex)
        else:
            dot_pdf_regex = QtCore.QRegExp(r".*\.[Pp][Dd][Ff]")  # type: ignore [assignment]
            validator = QtGui.QRegExpValidator(dot_pdf_regex)  # type: ignore [call-overload]
        self.safe_extension.setValidator(validator)
        self.safe_extension_layout = QtWidgets.QHBoxLayout()
        self.safe_extension_layout.addWidget(self.save_checkbox)
        self.safe_extension_layout.addWidget(self.safe_extension_label)
        self.safe_extension_layout.addLayout(self.safe_extension_name_layout)
        self.safe_extension_layout.addWidget(self.safe_extension_invalid)
        self.safe_extension_layout.addStretch()

        # Save safe to...
        self.save_label = QLabelClickable("Save safe PDFs to")
        self.save_location = QtWidgets.QLineEdit()
        self.save_location.setReadOnly(True)
        self.save_browse_button = QtWidgets.QPushButton("Choose...")
        self.save_browse_button.clicked.connect(self.select_output_directory)
        self.save_location_layout = QtWidgets.QHBoxLayout()
        self.save_location_layout.setContentsMargins(20, 0, 0, 0)
        self.save_location_layout.addWidget(self.save_label)
        self.save_location_layout.addWidget(self.save_location)
        self.save_location_layout.addWidget(self.save_browse_button)
        self.save_location_layout.addStretch()

        # 'Save PDF to' group box
        save_group_box_innner_layout = QtWidgets.QVBoxLayout()
        save_group_box = QtWidgets.QGroupBox()
        save_group_box.setLayout(save_group_box_innner_layout)
        save_group_box_layout = QtWidgets.QHBoxLayout()
        save_group_box_layout.setContentsMargins(20, 0, 0, 0)
        save_group_box_layout.addWidget(save_group_box)
        self.radio_move_untrusted = QtWidgets.QRadioButton(
            "Move original documents to 'unsafe' subdirectory"
        )
        save_group_box_innner_layout.addWidget(self.radio_move_untrusted)
        self.radio_save_to = QtWidgets.QRadioButton()
        self.save_label.clicked.connect(
            lambda: self.radio_save_to.setChecked(True)
        )  # select the radio button when label is clicked
        self.radio_save_to.setMinimumHeight(30)  # make the QTextEdit fully visible
        self.radio_save_to.setLayout(self.save_location_layout)
        save_group_box_innner_layout.addWidget(self.radio_save_to)

        # Open safe document
        if platform.system() in ["Darwin", "Windows"]:
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

        open_layout = QtWidgets.QHBoxLayout()
        open_layout.addWidget(self.open_checkbox)
        if platform.system() == "Linux":
            open_layout.addWidget(self.open_combobox)
        open_layout.addStretch()

        # OCR document
        self.ocr_checkbox = QtWidgets.QCheckBox("OCR document language")
        self.ocr_combobox = QtWidgets.QComboBox()
        for k in self.dangerzone.ocr_languages:
            self.ocr_combobox.addItem(k, self.dangerzone.ocr_languages[k])
        ocr_layout = QtWidgets.QHBoxLayout()
        ocr_layout.addWidget(self.ocr_checkbox)
        ocr_layout.addWidget(self.ocr_combobox)
        ocr_layout.addStretch()

        # Button
        self.start_button = QtWidgets.QPushButton()
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
        layout.addWidget(self.docs_selected_label)
        layout.addLayout(self.safe_extension_layout)
        layout.addLayout(save_group_box_layout)
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

        if self.dangerzone.settings.get("archive"):
            self.radio_move_untrusted.setChecked(True)
        else:
            self.radio_save_to.setChecked(True)

        if self.dangerzone.settings.get("ocr"):
            self.ocr_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.ocr_checkbox.setCheckState(QtCore.Qt.Unchecked)

        index = self.ocr_combobox.findText(self.dangerzone.settings.get("ocr_language"))
        if index != -1:
            self.ocr_combobox.setCurrentIndex(index)

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

    def check_writeable_archive_dir(self, docs: List[Document]) -> None:
        # assumed all documents are in the same directory
        first_doc = docs[0]
        try:
            first_doc.validate_default_archive_dir()
        except errors.UnwriteableArchiveDirException:
            self.radio_move_untrusted.setDisabled(True)
            self.radio_move_untrusted.setChecked(False)
            self.radio_move_untrusted.setToolTip(
                'Option disabled because Dangerzone couldn\'t create "untrusted"\n'
                + "subdirectory in the same directory as the original files."
            )
            self.radio_save_to.setChecked(True)

    def update_ui(self) -> None:
        conversion_readiness_conditions = [
            self.check_safe_extension_is_valid(),
            self.check_either_save_or_open(),
        ]
        if all(conversion_readiness_conditions):
            self.start_button.setEnabled(True)
        else:
            self.start_button.setDisabled(True)

    def documents_added(self, new_docs: List[Document]) -> None:
        self.save_location.setText(os.path.basename(self.dangerzone.output_dir))
        self.update_doc_n_labels()

        self.update_ui()

        # validations
        self.check_writeable_archive_dir(new_docs)

    def update_doc_n_labels(self) -> None:
        """Updates labels dependent on the number of present documents"""
        n_docs = len(self.dangerzone.get_unconverted_documents())

        if n_docs == 1:
            self.start_button.setText("Convert to Safe Document")
            self.docs_selected_label.setText(f"1 document selected")
        else:
            self.start_button.setText("Convert to Safe Documents")
            self.docs_selected_label.setText(f"{n_docs} documents selected")

    def select_output_directory(self) -> None:
        dialog = QtWidgets.QFileDialog()
        dialog.setLabelText(QtWidgets.QFileDialog.Accept, "Select output directory")

        # open the directory where the user last saved it
        dialog.setDirectory(self.dangerzone.output_dir)

        # Allow only the selection of directories
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)

        if dialog.exec_() == QtWidgets.QFileDialog.Accepted:
            selected_dir = dialog.selectedFiles()[0]
            if selected_dir is not None:
                self.dangerzone.output_dir = str(selected_dir)
                self.save_location.setText(selected_dir)

    def start_button_clicked(self) -> None:
        for document in self.dangerzone.get_unconverted_documents():
            if self.save_checkbox.isChecked():
                # If we're saving the document, set the suffix that the user chose. Then
                # check if we should to store the document in the same directory, and
                # move the original document to an 'unsafe' subdirectory, or save the
                # document to another directory.
                document.suffix = self.safe_extension.text()
                if self.radio_move_untrusted.isChecked():
                    document.archive_after_conversion = True
                elif self.radio_save_to.isChecked():
                    document.set_output_dir(self.dangerzone.output_dir)
            else:
                # If not saving, then save it to a temp file instead
                (_, tmp) = tempfile.mkstemp(suffix=".pdf", prefix="dangerzone_")
                document.output_filename = tmp

        # Update settings
        self.dangerzone.settings.set(
            "save", self.save_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.dangerzone.settings.set("safe_extension", self.safe_extension.text())
        self.dangerzone.settings.set("archive", self.radio_move_untrusted.isChecked())
        self.dangerzone.settings.set(
            "ocr", self.ocr_checkbox.checkState() == QtCore.Qt.Checked
        )
        self.dangerzone.settings.set("ocr_language", self.ocr_combobox.currentText())
        self.dangerzone.settings.set(
            "open", self.open_checkbox.checkState() == QtCore.Qt.Checked
        )
        if platform.system() == "Linux":
            self.dangerzone.settings.set("open_app", self.open_combobox.currentText())
        self.dangerzone.settings.save()

        # Start!
        self.start_clicked.emit()


class ConvertTask(QtCore.QObject):
    finished = QtCore.Signal(bool)
    update = QtCore.Signal(bool, str, int)

    def __init__(
        self,
        dangerzone: DangerzoneGui,
        document: Document,
        ocr_lang: Optional[str] = None,
    ) -> None:
        super(ConvertTask, self).__init__()
        self.document = document
        self.ocr_lang = ocr_lang
        self.error = False
        self.dangerzone = dangerzone

    def convert_document(self) -> None:
        self.dangerzone.isolation_provider.convert(
            self.document,
            self.ocr_lang,
            self.stdout_callback,
        )
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

        # Initialize thread_pool only on the first conversion
        # to ensure docker-daemon detection logic runs first
        self.thread_pool_initized = False

    def documents_added(self, new_docs: List[Document]) -> None:
        for document in new_docs:
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(500, 50))
            widget = DocumentWidget(self.dangerzone, document)
            self.addItem(item)
            self.setItemWidget(item, widget)
            self.document_widgets.append(widget)

    def start_conversion(self) -> None:
        if not self.thread_pool_initized:
            max_jobs = self.dangerzone.isolation_provider.get_max_parallel_conversions()
            self.thread_pool = ThreadPool(max_jobs)

        for doc_widget in self.document_widgets:
            task = ConvertTask(
                self.dangerzone, doc_widget.document, self.get_ocr_lang()
            )
            task.update.connect(doc_widget.update_progress)
            task.finished.connect(doc_widget.all_done)
            self.thread_pool.apply_async(task.convert_document)

    def get_ocr_lang(self) -> Optional[str]:
        ocr_lang = None
        if self.dangerzone.settings.get("ocr"):
            ocr_lang = self.dangerzone.ocr_languages[
                self.dangerzone.settings.get("ocr_language")
            ]
        return ocr_lang


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
        self.dangerous_doc_label.setAlignment(
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft
        )
        self.dangerous_doc_label.setText(os.path.basename(self.document.input_filename))
        self.dangerous_doc_label.setMinimumWidth(200)
        self.dangerous_doc_label.setMaximumWidth(200)

        # Conversion status images
        self.img_status_unconverted = self.load_status_image("status_unconverted.png")
        self.img_status_converting = self.load_status_image("status_converting.png")
        self.img_status_failed = self.load_status_image("status_failed.png")
        self.img_status_safe = self.load_status_image("status_safe.png")
        self.status_image = QtWidgets.QLabel()
        self.status_image.setMaximumWidth(15)
        self.status_image.setPixmap(self.img_status_unconverted)

        # Error label
        self.error_label = QtWidgets.QLabel()
        self.error_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.error_label.setWordWrap(True)
        self.error_label.hide()  # only show on error

        # Progress bar
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        # Layout
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.status_image)
        layout.addWidget(self.dangerous_doc_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.error_label)
        self.setLayout(layout)

    def update_progress(self, error: bool, text: str, percentage: int) -> None:
        self.update_status_image()
        if error:
            self.error = True
            self.error_label.setText(text)
            self.error_label.setToolTip(text)
            self.error_label.show()
            self.progress.hide()
        else:
            self.progress.setToolTip(text)
            self.progress.setValue(percentage)

    def load_status_image(self, filename: str) -> QtGui.QPixmap:
        path = get_resource_path(filename)
        img = QtGui.QImage(path)
        image = QtGui.QPixmap.fromImage(img)
        return image.scaled(QtCore.QSize(15, 15))

    def update_status_image(self) -> None:
        if self.document.is_unconverted():
            self.status_image.setPixmap(self.img_status_unconverted)
        elif self.document.is_converting():
            self.status_image.setPixmap(self.img_status_converting)
        elif self.document.is_failed():
            self.status_image.setPixmap(self.img_status_failed)
        elif self.document.is_safe():
            self.status_image.setPixmap(self.img_status_safe)

    def all_done(self) -> None:
        self.update_status_image()

        if self.error:
            return

        # Open
        if self.dangerzone.settings.get("open"):
            self.dangerzone.open_pdf_viewer(self.document.output_filename)


class QLabelClickable(QtWidgets.QLabel):
    """QLabel with a 'clicked' event"""

    clicked = QtCore.Signal()

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        self.clicked.emit()
