import json
import logging
import os
import sys
from typing import Optional

import click
from colorama import Fore, Style

from .common import Common
from .container import convert
from .global_common import GlobalCommon


def print_header(s: str) -> None:
    click.echo("")
    click.echo(Style.BRIGHT + s)


@click.command()
@click.option("--output-filename", help="Default is filename ending with -safe.pdf")
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.argument("filename", required=True)
def cli_main(
    output_filename: Optional[str], ocr_lang: Optional[str], filename: str
) -> None:
    setup_logging()
    global_common = GlobalCommon()
    common = Common()

    global_common.display_banner()

    # Validate filename
    valid = True
    try:
        with open(os.path.abspath(filename), "rb") as f:
            pass
    except:
        valid = False

    if not valid:
        click.echo("Invalid filename")
        exit(1)

    common.input_filename = os.path.abspath(filename)

    # Validate safe PDF output filename
    if output_filename:
        valid = True
        if not output_filename.endswith(".pdf"):
            click.echo("Safe PDF filename must end in '.pdf'")
            exit(1)

        try:
            with open(os.path.abspath(output_filename), "wb"):
                pass
        except:
            valid = False

        if not valid:
            click.echo("Safe PDF filename is not writable")
            exit(1)

        common.output_filename = os.path.abspath(output_filename)

    else:
        common.output_filename = (
            f"{os.path.splitext(common.input_filename)[0]}-safe.pdf"
        )
        try:
            with open(common.output_filename, "wb"):
                pass
        except:
            click.echo(
                f"Output filename {common.output_filename} is not writable, use --output-filename"
            )
            exit(1)

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
    global_common.install_container()

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
        common.input_filename,
        common.output_filename,
        ocr_lang,
        stdout_callback,
    ):
        print_header("Safe PDF created successfully")
        click.echo(common.output_filename)
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
