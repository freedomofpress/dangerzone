import os
import shutil
import click
import colorama
from colorama import Fore, Back, Style

from .global_common import GlobalCommon
from .common import Common
from dangerzone import global_common


def display_banner(global_common):
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
    colorama.init(autoreset=True)
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
    left_spaces = (15 - len(global_common.version) - 1) // 2
    right_spaces = left_spaces
    if left_spaces + len(global_common.version) + 1 + right_spaces < 15:
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
        + f"{' '*left_spaces}Dangerzone v{global_common.version}{' '*right_spaces}"
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
    print(Fore.YELLOW + Style.DIM + "╰──────────────────────────╯")


def exec_container(global_common, args):
    output = ""

    with global_common.exec_dangerzone_container(args) as p:
        for line in p.stdout:
            output += line.decode()
            print(line.decode(), end="")

        stderr = p.stderr.read().decode()
        print(stderr)

    if p.returncode == 126 or p.returncode == 127:
        click.echo(f"Authorization failed")
    elif p.returncode == 0:
        click.echo(f"Return code: {p.returncode}")

    print("")
    return p.returncode, output, stderr


@click.command()
@click.option("--custom-container", help="Use a custom container")
@click.option("--safe-pdf-filename", help="Default is filename ending with -safe.pdf")
@click.option("--ocr-lang", help="Language to OCR, defaults to none")
@click.option(
    "--skip-update",
    is_flag=True,
    help="Don't update flmcode/dangerzone container",
)
@click.argument("filename", required=True)
def cli_main(custom_container, safe_pdf_filename, ocr_lang, skip_update, filename):
    global_common = GlobalCommon()
    common = Common()

    display_banner(global_common)

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
    if safe_pdf_filename:
        valid = True
        if not safe_pdf_filename.endswith(".pdf"):
            click.echo("Safe PDF filename must end in '.pdf'")
            return

        try:
            with open(os.path.abspath(safe_pdf_filename), "wb") as f:
                pass
        except:
            valid = False

        if not valid:
            click.echo("Safe PDF filename is not writable")
            return

        common.save_filename = os.path.abspath(safe_pdf_filename)

    else:
        common.save_filename = (
            f"{os.path.splitext(common.document_filename)[0]}-safe.pdf"
        )
        try:
            with open(common.save_filename, "wb") as f:
                pass
        except:
            click.echo(
                f"Output filename {common.save_filename} is not writable, use --safe-pdf-filename"
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

    # Validate custom container
    if custom_container:
        success, error_message = global_common.container_exists(custom_container)
        if not success:
            click.echo(error_message)
            return

        global_common.custom_container = custom_container
    else:
        if skip_update:
            # Make sure flmcode/dangerzone exists
            success, error_message = global_common.container_exists(
                "flmcode/dangerzone"
            )
            if not success:
                click.echo(
                    "You don't have the flmcode/dangerzone container so you can't use --skip-update"
                )
                return

    # Pull the latest image
    if not skip_update:
        click.echo("Pulling container image (this might take a few minutes)")
        returncode, _, _ = exec_container(global_common, ["pull"])
        if returncode != 0:
            return

    # Convert to pixels
    click.echo("Converting document to pixels")
    returncode, output, _ = exec_container(
        global_common,
        [
            "documenttopixels",
            "--document-filename",
            common.document_filename,
            "--pixel-dir",
            common.pixel_dir.name,
            "--container-name",
            global_common.get_container_name(),
        ],
    )

    if returncode != 0:
        return

    success, error_message = global_common.validate_convert_to_pixel_output(
        common, output
    )
    if not success:
        click.echo(error_message)
        return

    # Convert to PDF
    click.echo("Converting pixels to safe PDF")

    if ocr_lang:
        ocr = "1"
    else:
        ocr = "0"
        ocr_lang = ""

    returncode, _, _ = exec_container(
        global_common,
        [
            "pixelstopdf",
            "--pixel-dir",
            common.pixel_dir.name,
            "--safe-dir",
            common.safe_dir.name,
            "--container-name",
            global_common.get_container_name(),
            "--ocr",
            ocr,
            "--ocr-lang",
            ocr_lang,
        ],
    )

    if returncode != 0:
        return

    # Save the safe PDF
    source_filename = f"{common.safe_dir.name}/safe-output-compressed.pdf"
    shutil.move(source_filename, common.save_filename)
    print(f"Success! {common.save_filename}")
