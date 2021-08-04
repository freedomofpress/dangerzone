import os
import shutil
import click
from colorama import Fore, Back, Style

from .global_common import GlobalCommon
from .common import Common


def print_header(s):
    click.echo("")
    click.echo(Style.BRIGHT + s)


def exec_container(global_common, args):
    output = ""

    with global_common.exec_dangerzone_container(args) as p:
        for line in p.stdout:
            output += line.decode()

            # Hack to add colors to the command executing
            if line.startswith(b"> "):
                print(
                    Style.DIM + "> " + Style.NORMAL + Fore.CYAN + line.decode()[2:],
                    end="",
                )
            else:
                print("  " + line.decode(), end="")

        stderr = p.stderr.read().decode()
        if len(stderr) > 0:
            print("")
            for line in stderr.strip().split("\n"):
                print("  " + Style.DIM + line)

    if p.returncode != 0:
        click.echo(f"Return code: {p.returncode}")
        if p.returncode == 126 or p.returncode == 127:
            click.echo(f"Authorization failed")

    return p.returncode, output, stderr


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

    common.document_filename = os.path.abspath(filename)

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
            f"{os.path.splitext(common.document_filename)[0]}-safe.pdf"
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
    if not global_common.is_container_installed():
        global_common.install_container()

    # Convert the document
    print_header("Converting document to safe PDF")

    if ocr_lang:
        ocr = "1"
    else:
        ocr = "0"
        ocr_lang = ""

    returncode, output, _ = exec_container(
        global_common,
        [
            "convert",
            "--input-filename",
            common.document_filename,
            "--output-filename",
            common.output_filename,
            "--ocr",
            ocr,
            "--ocr-lang",
            ocr_lang,
        ],
    )

    if returncode != 0:
        return

    # success, error_message = global_common.validate_convert_to_pixel_output(
    #     common, output
    # )
    # if not success:
    #     click.echo(error_message)
    #     return

    print_header("Safe PDF created successfully")
    click.echo(common.output_filename)
