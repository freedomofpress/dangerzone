import logging
import platform
import sys
from typing import List, Optional

import click
from colorama import Back, Fore, Style

from . import args, errors, startup
from .document import ARCHIVE_SUBDIR, SAFE_EXTENSION
from .isolation_provider.container import Container
from .isolation_provider.dummy import Dummy
from .isolation_provider.qubes import Qubes, is_qubes_native_conversion
from .logic import DangerzoneCore
from .podman.machine import PodmanMachineManager
from .settings import Settings
from .updater import install
from .util import get_version, replace_control_chars


def print_header(s: str) -> None:
    click.echo("")
    click.echo(Style.BRIGHT + s)


@click.command()
@click.option(
    "--output-filename",
    callback=args.validate_output_filename,
    help=f"Default is filename ending with {SAFE_EXTENSION}",
)
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.option(
    "--archive",
    "archive",
    flag_value=True,
    help=f"Archives the unsafe version in a subdirectory named '{ARCHIVE_SUBDIR}'",
)
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
@click.option(
    "--debug",
    "debug",
    flag_value=True,
    help="Run Dangerzone in debug mode, to get logs from gVisor.",
)
@click.option(
    "--set-container-runtime",
    required=False,
    help=(
        "The name or full path of the container runtime you want Dangerzone to use."
        " You can specify the value 'default' if you want to take back your choice, and"
        " let Dangerzone use the default runtime for this OS"
    ),
)
@click.option(
    "--linger",
    flag_value=True,
    help=(
        "Do not stop the Podman machine VM that Dangerzone uses to run containers,"
        " after the conversions have completed. This is useful if you want to run"
        " multiple conversions in a row, since the startup of the VM takes some time."
        " If you choose to let the Podman machine linger, you will need to stop it"
        " manually with `dangerzone-machine stop`. This option affects only"
        " Windows/macOS platforms."
    ),
)
@click.version_option(version=get_version(), message="%(version)s")
@errors.handle_document_errors
def cli_main(
    output_filename: Optional[str],
    ocr_lang: Optional[str],
    filenames: Optional[List[str]],
    archive: bool,
    dummy_conversion: bool,
    debug: bool,
    set_container_runtime: Optional[str] = None,
    linger: bool = False,
) -> None:
    setup_logging()
    # FIXME: This creates an issue in Windows CI tests, so we temporarily disable it
    # until we find the root cause.
    # display_banner()
    settings = Settings(debug=debug)
    if set_container_runtime:
        if set_container_runtime == "default":
            settings.unset_custom_runtime()
            click.echo(
                "Instructed Dangerzone to use the default container runtime for this OS"
            )
        else:
            container_runtime = settings.set_custom_runtime(
                set_container_runtime, autosave=True
            )
            click.echo(f"Set the settings container_runtime to {container_runtime}")
        sys.exit(0)
    elif not filenames:
        raise click.UsageError("Missing argument 'FILENAMES...'")

    if getattr(sys, "dangerzone_dev", False) and dummy_conversion:
        dangerzone = DangerzoneCore(Dummy())
    elif is_qubes_native_conversion():
        dangerzone = DangerzoneCore(Qubes())
    else:
        dangerzone = DangerzoneCore(Container(debug=debug))

    if len(filenames) == 1 and output_filename:
        dangerzone.add_document_from_filename(filenames[0], output_filename, archive)
    elif len(filenames) > 1 and output_filename:
        click.echo("--output-filename can only be used with one input file.")
        sys.exit(1)
    else:
        for filename in filenames:
            dangerzone.add_document_from_filename(filename, archive=archive)

    # Validate OCR language
    if ocr_lang:
        valid = False
        for lang in dangerzone.ocr_languages:
            if dangerzone.ocr_languages[lang] == ocr_lang:
                valid = True
                break
        if not valid:
            click.echo("Invalid OCR language code. Valid language codes:")
            for lang in dangerzone.ocr_languages:
                click.echo(f"{dangerzone.ocr_languages[lang]}: {lang}")
            sys.exit(1)

    tasks = []
    if dangerzone.isolation_provider.requires_install():
        tasks = [
            startup.MachineInitTask(),
            startup.MachineStartTask(),
            startup.UpdateCheckTask(),
            startup.ContainerInstallTask(),
        ]
    startup.StartupLogic(tasks=tasks).run()

    # Convert the document
    print_header("Converting document to safe PDF")

    dangerzone.convert_documents(ocr_lang)
    documents_safe = dangerzone.get_safe_documents()
    documents_failed = dangerzone.get_failed_documents()

    if documents_safe != []:
        print_header("Safe PDF(s) created successfully")
        for document in documents_safe:
            click.echo(replace_control_chars(document.output_filename))

        if archive:
            print_header(
                f"Unsafe (original) documents moved to '{ARCHIVE_SUBDIR}' subdirectory"
            )

    if (
        dangerzone.isolation_provider.requires_install()
        and platform.system() != "Linux"
        and not linger
    ):
        click.echo("Stopping Podman machine...")
        PodmanMachineManager().stop()

    if documents_failed != []:
        print_header("Failed to convert document(s)")
        for document in documents_failed:
            click.echo(replace_control_chars(document.input_filename))
        sys.exit(1)
    else:
        sys.exit(0)


args.override_parser_and_check_suspicious_options(cli_main)


def setup_logging() -> None:
    class EndUserLoggingFormatter(logging.Formatter):
        """Prefixes any non-INFO log line with the log level"""

        def format(self, record: logging.LogRecord) -> str:
            if record.levelno == logging.INFO:
                # Bypass formatter: print line directly
                return record.getMessage()
            else:
                return super().format(record)

    if getattr(sys, "dangerzone_dev", False):
        fmt = "[%(levelname)-5s] %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        # prefix non-INFO log lines with the respective log type
        fmt = "%(levelname)s %(message)s"
        formatter = EndUserLoggingFormatter(fmt=fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(ch)


def display_banner() -> None:
    """
    Raw ASCII art example:
    ╭──────────────────────────╮
    │           ▄██▄           │
    │          ██████          │
    │         ███▀▀▀██         │
    │        ███   ████        │
    │       ███   ██████       │
    │      ███   ▀▀▀▀████      │
    │     ███████  ▄██████     │
    │    ███████ ▄█████████    │
    │   ████████████████████   │
    │    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    │
    │                          │
    │    Dangerzone v0.1.5     │
    │ https://dangerzone.rocks │
    ╰──────────────────────────╯
    """

    print(Back.BLACK + Fore.YELLOW + Style.DIM + "╭──────────────────────────╮")
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "           ▄██▄           "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "          ██████          "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "         ███▀▀▀██         "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "        ███   ████        "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "       ███   ██████       "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "      ███   ▀▀▀▀████      "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "     ███████  ▄██████     "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "    ███████ ▄█████████    "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "   ████████████████████   "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(Back.BLACK + Fore.YELLOW + Style.DIM + "│                          │")
    left_spaces = (15 - len(get_version()) - 1) // 2
    right_spaces = left_spaces
    if left_spaces + len(get_version()) + 1 + right_spaces < 15:
        right_spaces += 1
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Style.RESET_ALL
        + Back.BLACK
        + Fore.LIGHTWHITE_EX
        + Style.BRIGHT
        + f"{' ' * left_spaces}Dangerzone v{get_version()}{' ' * right_spaces}"
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Style.RESET_ALL
        + Back.BLACK
        + Fore.LIGHTWHITE_EX
        + " https://dangerzone.rocks "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "╰──────────────────────────╯"
        + Style.RESET_ALL
    )
