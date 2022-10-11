import json
import logging
import os
import sys
from typing import Optional

import click
from colorama import Back, Fore, Style

from . import args, container, errors
from .container import convert
from .document import Document
from .global_common import GlobalCommon
from .util import get_version


def print_header(s: str) -> None:
    click.echo("")
    click.echo(Style.BRIGHT + s)


@click.command()
@click.option(
    "--output-filename",
    callback=args.validate_output_filename,
    help="Default is filename ending with -safe.pdf",
)
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.argument("filename", required=True, callback=args.validate_input_filename)
@errors.handle_document_errors
def cli_main(
    output_filename: Optional[str], ocr_lang: Optional[str], filename: str
) -> None:
    setup_logging()
    global_common = GlobalCommon()

    display_banner()

    document = Document(os.path.abspath(filename))

    # Validate safe PDF output filename
    if output_filename:
        document.output_filename = os.path.abspath(output_filename)
    else:
        document.output_filename = (
            f"{os.path.splitext(document.input_filename)[0]}-safe.pdf"
        )

    # Validate OCR language
    if ocr_lang:
        valid = False
        for lang in global_common.ocr_languages:
            if global_common.ocr_languages[lang] == ocr_lang:
                valid = True
                break
        if not valid:
            click.echo("Invalid OCR language code. Valid language codes:")
            for lang in global_common.ocr_languages:
                click.echo(f"{global_common.ocr_languages[lang]}: {lang}")
            exit(1)

    # Ensure container is installed
    container.install()

    # Convert the document
    print_header("Converting document to safe PDF")

    def stdout_callback(line: str) -> None:
        try:
            status = json.loads(line)
            s = Style.BRIGHT + Fore.CYAN + f"{status['percentage']}% "
            if status["error"]:
                s += Style.RESET_ALL + Fore.RED + status["text"]
            else:
                s += Style.RESET_ALL + status["text"]
            click.echo(s)
        except:
            click.echo(f"Invalid JSON returned from container: {line}")

    if convert(
        document.input_filename,
        document.output_filename,
        ocr_lang,
        stdout_callback,
    ):
        print_header("Safe PDF created successfully")
        click.echo(document.output_filename)
        exit(0)
    else:
        print_header("Failed to convert document")
        exit(1)


def setup_logging() -> None:
    if getattr(sys, "dangerzone_dev", True):
        fmt = "%(message)s"
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        logging.basicConfig(level=logging.ERROR, format=fmt)


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
        + f"{' '*left_spaces}Dangerzone v{get_version()}{' '*right_spaces}"
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
    print(Back.BLACK + Fore.YELLOW + Style.DIM + "╰──────────────────────────╯")
