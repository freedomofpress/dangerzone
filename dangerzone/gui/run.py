import os
import platform
import signal
import sys
from typing import List, Optional

import click
import colorama

from .. import args, errors
from ..document import Document
from ..isolation_provider.container import Container
from ..isolation_provider.dummy import Dummy
from ..isolation_provider.qubes import Qubes, is_qubes_native_conversion
from ..settings import Settings
from ..util import get_version
from . import Application, setup_logging
from .logic import DangerzoneGui
from .main_window import MainWindow


@click.command()
@click.option(
    "--unsafe-dummy-conversion", "dummy_conversion", flag_value=True, hidden=True
)
@click.argument(
    "filenames",
    required=False,
    nargs=-1,
    type=click.UNPROCESSED,
    callback=args.validate_input_filenames,
)
@click.version_option(version=get_version(), message="%(version)s")
@errors.handle_document_errors
def run(dummy_conversion: bool, filenames: Optional[List[str]]) -> Optional[bool]:
    setup_logging()

    if platform.system() == "Darwin":
        # Required for macOS Big Sur: https://stackoverflow.com/a/64878899
        os.environ["QT_MAC_WANTS_LAYER"] = "1"

        # Make sure /usr/local/bin is in the path
        os.environ["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"

        # Don't show ANSI colors from stdout output, to prevent terminal
        # colors from breaking the macOS GUI app
        colorama.deinit()

    # Create the Qt app
    app = Application()

    # Common objects
    if getattr(sys, "dangerzone_dev", False) and dummy_conversion:
        dummy = Dummy()
        dangerzone = DangerzoneGui(app, isolation_provider=dummy)
    elif is_qubes_native_conversion():
        qubes = Qubes()
        dangerzone = DangerzoneGui(app, isolation_provider=qubes)
    else:
        container = Container()
        dangerzone = DangerzoneGui(app, isolation_provider=container)

    # Allow Ctrl-C to smoothly quit the program instead of throwing an exception
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    def open_files(filenames: List[str] = []) -> None:
        documents = [Document(filename) for filename in filenames]
        window.conversion_widget.doc_selection_widget.documents_selected.emit(documents)

    window = MainWindow(dangerzone)
    settings = Settings()
    updates_enabled = bool(settings.get("updater_check_all"))
    window.toggle_updates_action.setChecked(updates_enabled)
    window.startup_thread.start()

    if filenames:
        open_files(filenames)

    # MacOS: Open a new window, if all windows are closed
    def application_activated() -> None:
        window.show()
        window.adjustSize()

    # If we get a file open event, open it
    app.document_selected.connect(open_files)

    # If the application is activated and all windows are closed, open a new one
    app.application_activated.connect(application_activated)

    # Launch the GUI
    ret = app.exec_()

    sys.exit(ret)


args.override_parser_and_check_suspicious_options(run)
