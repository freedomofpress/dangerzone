import logging
import sys

import click
from colorama import Back, Fore, Style

from . import args, errors, shutdown, startup
from .document import ARCHIVE_SUBDIR, SAFE_EXTENSION
from .isolation_provider.container import Container
from .isolation_provider.dummy import Dummy
from .isolation_provider.qubes import Qubes, is_qubes_native_conversion
from .logic import DangerzoneCore
from .settings import Settings
from .util import get_version, replace_control_chars


def print_header(s: str) -> None:
    click.echo("", err=True)
    click.echo(Style.BRIGHT + s, err=True)


def _read_stdin() -> bytes:
    """Read all bytes from stdin."""
    return sys.stdin.buffer.read()


def _initialize_documents(
    dangerzone: DangerzoneCore,
    filenames: list[str] | None,
    archive: bool,
    output_filename: str | None,
) -> None:
    """Validate that options are compatible with stdin input."""
    if len(filenames) > 1:
        if "-" in filenames:
            raise click.BadArgumentUsage(
                "Cannot mix input from stdin with other documents"
            )
        if output_filename:
            raise click.BadOptionUsage(
                "--output-filename can only be used with one input file"
            )

    if output_filename is None and sys.stdout.isatty():
        raise click.UsageError(
            "Cowardly refusing to write to a terminal.\n"
            "Use --output-filename to specify an output file, or redirect "
            "stdout to a file/pipe."
        )

    if filenames == ["-"] or not filenames:
        # We are reading a single document from stdin.
        if archive:
            raise click.UsageError("--archive cannot be used with input from stdin")
        if sys.stdin.isatty():
            raise click.UsageError("No files were provided and cannot read from stdin")
        dangerzone.add_document_from_stdin(output_filename)
        return

    for filename in filenames:
        dangerzone.add_document_from_filename(filename, output_filename, archive)


@click.command(
    help=(
        "Convert potentially dangerous documents to safe PDFs.\n\n"
        "Accepts file paths as arguments, or reads from stdin when no\n"
        "files are given (or when '-' is passed as a filename). When\n"
        "reading from stdin, the safe PDF is written to stdout unless\n"
        "--output-filename is specified. All status output goes to stderr."
    )
)
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
def run(
    output_filename: str | None,
    ocr_lang: str | None,
    filenames: list[str] | None,
    archive: bool,
    dummy_conversion: bool,
    debug: bool,
    set_container_runtime: str | None = None,
    linger: bool = False,
) -> None:
    setup_logging()
    display_banner()
    settings = Settings(debug=debug)
    if set_container_runtime:
        if set_container_runtime == "default":
            settings.unset_custom_runtime()
            click.echo(
                "Instructed Dangerzone to use the default container runtime for this OS",
                err=True,
            )
        else:
            container_runtime = settings.set_custom_runtime(
                set_container_runtime, autosave=True
            )
            click.echo(
                f"Set the settings container_runtime to {container_runtime}", err=True
            )
        sys.exit(0)

    if getattr(sys, "dangerzone_dev", False) and dummy_conversion:
        dangerzone = DangerzoneCore(Dummy())
    elif is_qubes_native_conversion():
        dangerzone = DangerzoneCore(Qubes())
    else:
        dangerzone = DangerzoneCore(Container(debug=debug))

    _initialize_documents(dangerzone, filenames, archive, output_filename)

    # Validate OCR language
    if ocr_lang:
        valid = False
        for lang in dangerzone.ocr_languages:
            if dangerzone.ocr_languages[lang] == ocr_lang:
                valid = True
                break
        if not valid:
            click.echo("Invalid OCR language code. Valid language codes:", err=True)
            for lang in dangerzone.ocr_languages:
                click.echo(f"{dangerzone.ocr_languages[lang]}: {lang}", err=True)
            sys.exit(1)

    tasks = []
    if dangerzone.isolation_provider.requires_install():
        tasks = [
            startup.WSLInstallTask(),
            startup.MachineStopOthersTask(),
            startup.MachineInitTask(),
            startup.MachineStartTask(),
            startup.UpdateCheckTask(),
            startup.ContainerInstallTask(),
        ]

    try:
        try:
            startup.StartupLogic(tasks=tasks).run()
        except errors.UpdaterDisabledNoContainer:
            click.echo(
                "\n"
                + Fore.RED
                + Style.BRIGHT
                + "No container image found."
                + Style.RESET_ALL
                + " Please initialize Dangerzone by running:\n\n"
                "    dangerzone-image upgrade\n",
                err=True,
            )
            sys.exit(1)
        print_header("Converting document(s) to safe PDF")
        dangerzone.convert_documents(ocr_lang)
    finally:
        if dangerzone.isolation_provider.requires_install() and not linger:
            task_container_stop = shutdown.ContainerStopTask()
            task_machine_stop = shutdown.MachineStopTask()
            tasks = [task_container_stop, task_machine_stop]
            shutdown.ShutdownLogic(tasks=tasks).run()

    documents_safe = dangerzone.get_safe_documents()
    documents_failed = dangerzone.get_failed_documents()

    if documents_safe != []:
        print_header("Safe PDF(s) created successfully")
        for document in documents_safe:
            # When writing to stdout (data-based doc, no output filename),
            # skip printing the filename — the PDF is already on stdout.
            if document._data is None or document._output_filename is not None:
                click.echo(replace_control_chars(document.output_filename), err=True)

        if archive:
            print_header(
                f"Unsafe (original) documents moved to '{ARCHIVE_SUBDIR}' subdirectory"
            )

    if documents_failed != []:
        print_header("Failed to convert document(s)")
        for document in documents_failed:
            click.echo(replace_control_chars(str(document)), err=True)
        sys.exit(1)
    sys.exit(0)


args.override_parser_and_check_suspicious_options(run)


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
