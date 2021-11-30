import os
import sys
import json
import click
from colorama import Fore, Style

from .global_common import GlobalCommon
from .common import Common
from .container import convert


def print_header(s):
    click.echo("")
    click.echo(Style.BRIGHT + s)


@click.command()
@click.option("--output-filename", help="Default is filename ending with -safe.pdf")
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.argument("filename", required=True)
def cli_main(output_filename, ocr_lang, filename):
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
        return

    common.input_filename = os.path.abspath(filename)

    # Validate safe PDF output filename
    if output_filename:
        valid = True
        if not output_filename.endswith(".pdf"):
            click.echo("Safe PDF filename must end in '.pdf'")
            return

        try:
            with open(os.path.abspath(output_filename), "wb") as f:
                pass
        except:
            valid = False

        if not valid:
            click.echo("Safe PDF filename is not writable")
            return

        common.output_filename = os.path.abspath(output_filename)

    else:
        common.output_filename = (
            f"{os.path.splitext(common.input_filename)[0]}-safe.pdf"
        )
        try:
            with open(common.output_filename, "wb") as f:
                pass
        except:
            click.echo(
                f"Output filename {common.output_filename} is not writable, use --output-filename"
            )
            return

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
            return

    # Ensure container is installed
    global_common.install_container()

    # Convert the document
    print_header("Converting document to safe PDF")

    def stdout_callback(line):
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
        sys.exit(0)
    else:
        print_header("Failed to convert document")
        sys.exit(-1)
