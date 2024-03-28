import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import typing
from multiprocessing.pool import ThreadPool
from typing import Dict, List, Optional

from colorama import Fore, Style

# FIXME: See https://github.com/freedomofpress/dangerzone/issues/320 for more details.
if typing.TYPE_CHECKING:
    from PySide2 import QtCore, QtGui, QtSvg, QtWidgets
else:
    try:
        from PySide6 import QtCore, QtGui, QtSvg, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtSvg, QtWidgets

from .. import errors
from ..document import SAFE_EXTENSION, Document
from ..isolation_provider.container import Container, NoContainerTechException
from ..isolation_provider.dummy import Dummy
from ..isolation_provider.qubes import Qubes, is_qubes_native_conversion
from ..util import get_resource_path, get_subprocess_startupinfo, get_version
from .logic import Alert, CollapsibleBox, DangerzoneGui, UpdateDialog
from .updater import UpdateReport

log = logging.getLogger(__name__)


UPDATE_SUCCESS_MSG_INTRO = """\
<p>A new Dangerzone version has been released.</p>
<p>Please visit our <a href="https://dangerzone.rocks#downloads">downloads page</a> to install this
update.</p>
"""


UPDATE_ERROR_MSG_INTRO = """\
<p><b>Something went wrong while checking for Dangerzone updates.<b></p>
<p>You are strongly advised to visit our
<a href="https://dangerzone.rocks#downloads">downloads page</a> and check for new
updates manually, or consult
<a href=https://github.com/freedomofpress/dangerzone/wiki/Updates>this webpage</a> for
common causes of errors. Alternatively, you can uncheck the "Check for updates" option
in our menu, if you are in an air-gapped environment and have another way of learning
about updates.</p>
"""


HAMBURGER_MENU_SIZE = 30


def load_svg_image(filename: str, width: int, height: int) -> QtGui.QPixmap:
    """Load an SVG image from a filename.

    This answer is basically taken from: https://stackoverflow.com/a/25689790
    """
    path = get_resource_path(filename)
    svg_renderer = QtSvg.QSvgRenderer(path)
    image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
    # Set the ARGB to 0 to prevent rendering artifacts
    image.fill(0x00000000)
    svg_renderer.render(QtGui.QPainter(image))
    pixmap = QtGui.QPixmap.fromImage(image)
    return pixmap


def get_supported_extensions() -> List[str]:
    supported_ext = [
        ".pdf",
        ".docx",
        ".doc",
        ".docm",
        ".xlsx",
        ".xls",
        ".pptx",
        ".ppt",
        ".odt",
        ".odg",
        ".odp",
        ".ods",
        ".epub",
        ".jpg",
        ".jpeg",
        ".gif",
        ".png",
        " .tif",
        ".tiff",
        ".bmp",
        ".pnm",
        ".pbm",
        ".ppm",
        ".svg",
    ]

    # XXX: We disable loading HWP/HWPX files on Qubes, because H2ORestart does not work there.
    # See:
    #
    # https://github.com/freedomofpress/dangerzone/issues/494
    hwp_filters = [".hwp", ".hwpx"]
    if is_qubes_native_conversion():
        supported_ext += hwp_filters

    return supported_ext


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(MainWindow, self).__init__()
        self.dangerzone = dangerzone
        self.updater_error: Optional[str] = None

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
        header_label = QtWidgets.QLabel("Dangerzone")
        header_label.setFont(self.dangerzone.fixed_font)
        header_label.setStyleSheet("QLabel { font-weight: bold; font-size: 50px; }")
        header_version_label = QtWidgets.QLabel(get_version())
        header_version_label.setProperty("class", "version")
        header_version_label.setAlignment(QtCore.Qt.AlignBottom)

        # Create the hamburger button, whose main purpose is to inform the user about
        # updates.
        self.hamburger_button = QtWidgets.QToolButton()
        self.hamburger_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.hamburger_button.setIcon(
            QtGui.QIcon(load_svg_image("hamburger_menu.svg", width=64, height=64))
        )
        self.hamburger_button.setFixedSize(HAMBURGER_MENU_SIZE, HAMBURGER_MENU_SIZE)
        self.hamburger_button.setIconSize(
            QtCore.QSize(HAMBURGER_MENU_SIZE, HAMBURGER_MENU_SIZE)
        )
        self.hamburger_button.setStyleSheet(
            "QToolButton::menu-indicator { image: none; }"
        )
        self.hamburger_button.setArrowType(QtCore.Qt.ArrowType.NoArrow)

        # Create the menu for the hamburger button
        hamburger_menu = QtWidgets.QMenu(self.hamburger_button)
        self.hamburger_button.setMenu(hamburger_menu)

        # Add the "Check for updates" action
        self.toggle_updates_action = hamburger_menu.addAction("Check for updates")
        self.toggle_updates_action.triggered.connect(self.toggle_updates_triggered)
        self.toggle_updates_action.setCheckable(True)
        self.toggle_updates_action.setChecked(
            bool(self.dangerzone.settings.get("updater_check"))
        )

        # Add the "Exit" action
        hamburger_menu.addSeparator()
        exit_action = hamburger_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addSpacing(
            HAMBURGER_MENU_SIZE
        )  # balance out hamburger to keep logo centered
        header_layout.addStretch()
        header_layout.addWidget(logo)
        header_layout.addSpacing(10)
        header_layout.addWidget(header_label)
        header_layout.addWidget(header_version_label)
        header_layout.addStretch()
        header_layout.addWidget(self.hamburger_button)
        header_layout.addSpacing(15)

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

        # Set the OS color mode as a property on the MainWindow, which is the closest
        # thing we have to a top-level container element akin to an HTML `<body>`.
        # This allows us to make QSS rules conditional on the OS color mode.
        self.setProperty("OSColorMode", self.dangerzone.app.os_color_mode.value)

        self.show()

    def show_update_success(self) -> None:
        """Inform the user about a new Dangerzone release."""
        version = self.dangerzone.settings.get("updater_latest_version")
        changelog = self.dangerzone.settings.get("updater_latest_changelog")

        changelog_widget = CollapsibleBox("What's New?")
        changelog_layout = QtWidgets.QVBoxLayout()
        changelog_text_box = QtWidgets.QTextBrowser()
        changelog_text_box.setHtml(changelog)
        changelog_text_box.setOpenExternalLinks(True)
        changelog_layout.addWidget(changelog_text_box)
        changelog_widget.setContentLayout(changelog_layout)

        update_widget = UpdateDialog(
            self.dangerzone,
            title=f"Dangerzone {version} has been released",
            intro_msg=UPDATE_SUCCESS_MSG_INTRO,
            middle_widget=changelog_widget,
            epilogue_msg=None,
            ok_text="Ok",
            has_cancel=False,
        )
        update_widget.exec_()

    def show_update_error(self) -> None:
        """Inform the user about an error during update checks"""
        assert self.updater_error is not None

        error_widget = CollapsibleBox("Error Details")
        error_layout = QtWidgets.QVBoxLayout()
        error_text_box = QtWidgets.QTextBrowser()
        error_text_box.setHtml(self.updater_error)
        error_layout.addWidget(error_text_box)
        error_widget.setContentLayout(error_layout)

        update_widget = UpdateDialog(
            self.dangerzone,
            title="Update check error",
            intro_msg=UPDATE_ERROR_MSG_INTRO,
            middle_widget=error_widget,
            ok_text="Close",
            has_cancel=False,
        )
        update_widget.exec_()

    def toggle_updates_triggered(self) -> None:
        """Change the underlying update check settings based on the user's choice."""
        check = self.toggle_updates_action.isChecked()
        self.dangerzone.settings.set("updater_check", check)
        self.dangerzone.settings.save()

    def handle_updates(self, report: UpdateReport) -> None:
        """Handle update reports from the update checker thread.

        See Updater.check_for_updates() to find the different types of reports that it
        may send back, depending on the outcome of an update check.
        """
        # If there are no new updates, reset the error counter (if any) and return.
        if report.empty():
            self.dangerzone.settings.set("updater_errors", 0, autosave=True)
            return

        hamburger_menu = self.hamburger_button.menu()

        if report.error:
            log.error(f"Encountered an error during an update check: {report.error}")
            errors = self.dangerzone.settings.get("updater_errors") + 1
            self.dangerzone.settings.set("updater_errors", errors)
            self.dangerzone.settings.save()
            self.updater_error = report.error

            # If we encounter more than three errors in a row, show a red notification
            # bubble. This way, we don't inform the user about intermittent errors.
            if errors < 3:
                log.debug(
                    f"Will not show an error yet since number of errors is low ({errors})"
                )
                return

            self.hamburger_button.setIcon(
                QtGui.QIcon(
                    load_svg_image(
                        "hamburger_menu_update_error.svg", width=64, height=64
                    )
                )
            )
            sep = hamburger_menu.insertSeparator(hamburger_menu.actions()[0])
            # FIXME: Add red bubble next to the text.
            error_action = QtGui.QAction("Update error", hamburger_menu)  # type: ignore [attr-defined]
            error_action.setIcon(
                QtGui.QIcon(
                    load_svg_image(
                        "hamburger_menu_update_dot_error.svg", width=64, height=64
                    )
                )
            )
            error_action.triggered.connect(self.show_update_error)
            hamburger_menu.insertAction(sep, error_action)
        else:
            log.debug(f"Handling new version: {report.version}")
            self.dangerzone.settings.set("updater_latest_version", report.version)
            self.dangerzone.settings.set("updater_latest_changelog", report.changelog)
            self.dangerzone.settings.set("updater_errors", 0)

            # FIXME: Save the settings to the filesystem only when they have really changed,
            # maybe with a dirty bit.
            self.dangerzone.settings.save()

            self.hamburger_button.setIcon(
                QtGui.QIcon(
                    load_svg_image(
                        "hamburger_menu_update_success.svg", width=64, height=64
                    )
                )
            )

            sep = hamburger_menu.insertSeparator(hamburger_menu.actions()[0])
            success_action = QtGui.QAction("New version available", hamburger_menu)  # type: ignore [attr-defined]
            success_action.setIcon(
                QtGui.QIcon(
                    load_svg_image(
                        "hamburger_menu_update_dot_available.svg", width=64, height=64
                    )
                )
            )
            success_action.triggered.connect(self.show_update_success)
            hamburger_menu.insertAction(sep, success_action)

    def register_update_handler(self, signal: QtCore.SignalInstance) -> None:
        signal.connect(self.handle_updates)

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
        self.doc_selection_widget = DocSelectionWidget(self.dangerzone)
        self.doc_selection_widget.documents_selected.connect(self.documents_selected)
        self.doc_selection_wrapper = DocSelectionDropFrame(
            self.dangerzone, self.doc_selection_widget
        )
        self.doc_selection_wrapper.documents_selected.connect(self.documents_selected)

        # Settings
        self.settings_widget = SettingsWidget(self.dangerzone)
        self.documents_added.connect(self.settings_widget.documents_added)
        self.settings_widget.start_clicked.connect(self.start_clicked)
        self.settings_widget.hide()

        # Convert
        self.documents_list = DocumentsListWidget(self.dangerzone)
        self.documents_added.connect(self.documents_list.documents_added)
        self.settings_widget.start_clicked.connect(self.documents_list.start_conversion)
        self.settings_widget.change_docs_clicked.connect(
            self.doc_selection_widget.dangerous_doc_button_clicked
        )
        self.documents_list.hide()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.settings_widget, stretch=1)
        layout.addWidget(self.documents_list, stretch=1)
        layout.addWidget(self.doc_selection_wrapper, stretch=1)
        self.setLayout(layout)

    def documents_selected(self, docs: List[Document]) -> None:
        if self.conversion_started:
            Alert(
                self.dangerzone,
                message="Dangerzone does not support adding documents after the conversion has started.",
                has_cancel=False,
            ).exec_()
            return

        # Ensure all files in batch are in the same directory
        dirnames = {os.path.dirname(doc.input_filename) for doc in docs}
        if len(dirnames) > 1:
            Alert(
                self.dangerzone,
                message="Dangerzone does not support adding documents from multiple locations.\n\n The newly added documents were ignored.",
                has_cancel=False,
            ).exec_()
            return

        # Clear previously selected documents
        self.dangerzone.clear_documents()
        self.documents_list.clear()
        self.dangerzone.output_dir = list(dirnames)[0]

        for doc in docs:
            self.dangerzone.add_document(doc)

        self.doc_selection_wrapper.hide()
        self.settings_widget.show()

        if len(docs) > 0:
            self.documents_added.emit(docs)

    def start_clicked(self) -> None:
        self.conversion_started = True
        self.settings_widget.hide()
        self.documents_list.show()


class DocSelectionWidget(QtWidgets.QWidget):
    documents_selected = QtCore.Signal(list)

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(DocSelectionWidget, self).__init__()
        self.dangerzone = dangerzone

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

        # Open Docs Dialog
        self.file_dialog = QtWidgets.QFileDialog()
        self.file_dialog.setWindowTitle("Open Documents")
        self.file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        self.file_dialog.setNameFilters(
            [f"Documents (*" + " *".join(get_supported_extensions()) + ")"]
        )

    def dangerous_doc_button_clicked(self) -> None:
        unconverted_docs = self.dangerzone.get_unconverted_documents()
        if len(unconverted_docs) > 0:
            # In case there were some already selected documents, open the dir of selected files
            first_doc_dir = os.path.dirname(unconverted_docs[0].input_filename)
            self.file_dialog.setDirectory(first_doc_dir)

        if self.file_dialog.exec():
            documents = [
                Document(filename) for filename in self.file_dialog.selectedFiles()
            ]
            self.documents_selected.emit(documents)
        else:
            # No files selected
            pass


class DocSelectionDropFrame(QtWidgets.QFrame):
    """
    HACK Docs selecting widget "drag-n-drop" border widget
    The border frame doesn't show around the whole widget
    unless there is another widget wrapping it
    """

    documents_selected = QtCore.Signal(list)

    def __init__(
        self, dangerzone: DangerzoneGui, docs_selection_widget: DocSelectionWidget
    ) -> None:
        super().__init__()

        self.dangerzone = dangerzone
        self.docs_selection_widget = docs_selection_widget

        # Drag and drop functionality
        self.setAcceptDrops(True)

        self.document_image_text = QtWidgets.QLabel(
            "Drag and drop\n documents here\n\n or"
        )
        self.document_image_text.setAlignment(QtCore.Qt.AlignCenter)
        self.document_image = QtWidgets.QLabel()
        self.document_image.setAlignment(QtCore.Qt.AlignCenter)
        self.document_image.setPixmap(
            load_svg_image("document.svg", width=20, height=24)
        )

        self.center_layout = QtWidgets.QVBoxLayout()
        self.center_layout.addWidget(self.document_image)
        self.center_layout.addWidget(self.document_image_text)
        self.center_layout.addWidget(self.docs_selection_widget)

        self.drop_layout = QtWidgets.QVBoxLayout()
        self.drop_layout.addStretch()
        self.drop_layout.addLayout(self.center_layout)
        self.drop_layout.addStretch()

        self.setLayout(self.drop_layout)

    def dragEnterEvent(self, ev: QtGui.QDragEnterEvent) -> None:
        ev.accept()

    def dragLeaveEvent(self, ev: QtGui.QDragLeaveEvent) -> None:
        ev.accept()

    def dropEvent(self, ev: QtGui.QDropEvent) -> None:
        ev.setDropAction(QtCore.Qt.CopyAction)
        documents = []
        for url_path in ev.mimeData().urls():
            doc_path = url_path.toLocalFile()
            doc_ext = os.path.splitext(doc_path)[1]
            if doc_ext in get_supported_extensions():
                documents += [Document(doc_path)]

        # Ignore when all docs are unsupported
        num_unsupported_docs = len(ev.mimeData().urls()) - len(documents)
        if len(documents) == 0 or num_unsupported_docs == len(ev.mimeData().urls()):
            return

        # Confirm with user when some docs were ignored
        if num_unsupported_docs > 0:
            if not self.prompt_continue_without(num_unsupported_docs):
                return
        self.documents_selected.emit(documents)

    def prompt_continue_without(self, num_unsupported_docs: int) -> int:
        """
        Prompt the use if they want to convert even though some files are not
        supported.
        """
        if num_unsupported_docs == 1:
            text = f"{num_unsupported_docs} file is not supported."
            ok_text = "Continue without this file"
        else:  # plural
            text = f"{num_unsupported_docs} files are not supported."
            ok_text = "Continue without these file"

        alert_widget = Alert(
            self.dangerzone,
            message=f"{text}\n The supported extensions are: "
            + ", ".join(get_supported_extensions()),
            ok_text=ok_text,
        )

        return alert_widget.exec_()


class SettingsWidget(QtWidgets.QWidget):
    start_clicked = QtCore.Signal()
    change_docs_clicked = QtCore.Signal()

    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super(SettingsWidget, self).__init__()
        self.dangerzone = dangerzone

        # Num Docs Selected
        self.docs_selected_label = QtWidgets.QLabel("No documents selected")
        self.docs_selected_label.setAlignment(QtCore.Qt.AlignCenter)
        self.docs_selected_label.setProperty("class", "docs-selection")
        self.change_selection_button = QtWidgets.QPushButton("Change Selection")
        self.change_selection_button.clicked.connect(self.change_docs_clicked.emit)

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
        layout_docs_selected = QtWidgets.QHBoxLayout()
        layout_docs_selected.addStretch()
        layout_docs_selected.addWidget(self.docs_selected_label)
        layout_docs_selected.addWidget(self.change_selection_button)
        layout_docs_selected.addStretch()
        layout.addLayout(layout_docs_selected)
        layout.addSpacing(20)
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

    def documents_added(self, docs: List[Document]) -> None:
        self.save_location.setText(os.path.basename(self.dangerzone.output_dir))
        self.update_doc_n_labels()

        self.update_ui()

        # validations
        self.check_writeable_archive_dir(docs)

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
            self.progress_callback,
        )
        self.finished.emit(self.error)

    def progress_callback(self, error: bool, text: str, percentage: int) -> None:
        if error:
            self.error = True

        self.update.emit(error, text, percentage)


class DocumentsListWidget(QtWidgets.QListWidget):
    def __init__(self, dangerzone: DangerzoneGui) -> None:
        super().__init__()
        self.dangerzone = dangerzone
        self.docs_list: List[Document] = []
        self.docs_list_widget_map: dict[Document, DocumentWidget] = {}

        # Initialize thread_pool only on the first conversion
        # to ensure docker-daemon detection logic runs first
        self.thread_pool_initized = False

    def clear(self) -> None:
        self.docs_list = []
        self.docs_list_widget_map = {}
        super().clear()

    def documents_added(self, docs: List[Document]) -> None:
        for document in docs:
            item = QtWidgets.QListWidgetItem()
            item.setSizeHint(QtCore.QSize(500, 50))
            widget = DocumentWidget(self.dangerzone, document)
            self.addItem(item)
            self.setItemWidget(item, widget)

            # Keep docs_list in sync with items list
            self.docs_list.append(document)
            self.docs_list_widget_map[document] = widget

    def start_conversion(self) -> None:
        if not self.thread_pool_initized:
            max_jobs = self.dangerzone.isolation_provider.get_max_parallel_conversions()
            self.thread_pool = ThreadPool(max_jobs)

        for doc in self.docs_list:
            task = ConvertTask(self.dangerzone, doc, self.get_ocr_lang())
            doc_widget = self.docs_list_widget_map[doc]
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
        self.error_label.setTextFormat(QtCore.Qt.PlainText)
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
