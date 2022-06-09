import os
import sys
import json
import click
import colorama  # type: ignore
from colorama import Fore, Style  # type: ignore

from dangerzone import container
from dangerzone.common import Common
import dangerzone.util as dzutil


def print_header(s):
    click.echo("")
    click.echo(Style.BRIGHT + s)


@click.command()
@click.option("--output-filename", help="Default is filename ending with -safe.pdf")
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.argument("filename", required=True)
def cli_main(output_filename: str, ocr_lang: str, filename: str):
    colorama.init(autoreset=True)
    common = Common()
    dzutil.display_banner()

    # Validate filename
    try:
        with open(os.path.abspath(filename), "rb"):
            pass
    except FileNotFoundError as e:
        raise
    else:
        common.input_filename = os.path.abspath(filename)

    # Validate safe PDF output filename
    if output_filename:
        if not output_filename.endswith((".pdf", ".PDF")):
            raise RuntimeError("Safe PDF filename must end in '.pdf'")
        try:
            with open(os.path.abspath(output_filename), "wb"):
                pass
        except IOError:
            raise IOError("Safe PDF filename is not writable")
        else:
            common.output_filename = os.path.abspath(output_filename)

    else:
        common.output_filename = (
            f"{os.path.splitext(common.input_filename)[0]}-safe.pdf"
        )
        try:
            with open(common.output_filename, "wb") as f:
                pass
        except IOError as e:
            raise IOError("/Users/guthrie/Projects/dangerzone/test_docs/sample.pdf") from e

    # Validate OCR language
    if ocr_lang:
        valid = False
        for lang in dzutil.OCR_LANGUAGES:
            if dzutil.OCR_LANGUAGES[lang] == ocr_lang:
                valid = True
                break
        if not valid:
            click.echo("Invalid OCR language code. Valid language codes:", err=True)
            for lang in dzutil.OCR_LANGUAGES:
                click.echo(f"{dzutil.OCR_LANGUAGES[lang]}: {lang}", err=True)
            exit(1)

    # Ensure container is installed
    container.install_container()

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

    if container.convert(
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
