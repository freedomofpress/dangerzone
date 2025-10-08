import logging
import os
import sys

logger = logging.getLogger(__name__)

basename = os.path.basename(sys.argv[0])

# Patch the stdlib early in the import tree in order to log background calls
# Only patch dangerzone and dangerzone-cli, to avoid capturing output for other
# commands (e.g. dangerzone-machine and dangerzone-image)
if basename in ["dangerzone-cli", "dangerzone", "dangerzone-cli.exe", "dangerzone.exe"]:
    from . import capture_output

    capture_output.patch_stdlib()

# Call freeze_support() to avoid passing unknown options to the subprocess.
# See https://github.com/freedomofpress/dangerzone/issues/873
import multiprocessing

multiprocessing.freeze_support()


try:
    from . import vendor  # type: ignore [attr-defined]

    vendor_path: str = vendor.__path__[0]
    logger.debug(f"Using vendored PyMuPDF libraries from '{vendor_path}'")
    sys.path.insert(0, vendor_path)
except ImportError:
    pass

if "DANGERZONE_MODE" in os.environ:
    mode = os.environ["DANGERZONE_MODE"]
else:
    cli_names = [
        "dangerzone-cli",
        "dangerzone-cli.exe",
        "dangerzone-image",
        "dangerzone-image.exe",
    ]
    if basename in cli_names:
        mode = "cli"
    else:
        mode = "gui"


if mode == "cli":
    from .cli import cli_main as main
else:
    from .gui import gui_main as main  # noqa: F401
