import click


@click.command()
@click.option("--custom-container")  # Use this container instead of flmcode/dangerzone
@click.argument("filename", required=False)
def cli_main(custom_container, filename):
    pass
