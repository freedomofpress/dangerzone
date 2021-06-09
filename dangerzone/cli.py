import click

from .global_common import GlobalCommon


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

    # Make sure custom container exists
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

    if not skip_update:
        click.echo("Pulling container image (this might take a few minutes)")
        returncode, _, _ = exec_container(global_common, ["pull"])
        if returncode != 0:
            return
