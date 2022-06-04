import os
import sys

import appdirs

CONTAINER_NAME = "dangerzone.rocks/dangerzone"
APPDATA_PATH = appdirs.user_config_dir("dangerzone")

if "DANGERZONE_MODE" in os.environ:
    mode = os.environ["DANGERZONE_MODE"]
else:
    basename = os.path.basename(sys.argv[0])
    if basename == "dangerzone-cli" or basename == "dangerzone-cli.exe":
        mode = "cli"
    else:
        mode = "gui"

if mode == "cli":
    from .cli import cli_main as main
else:
    from .gui import gui_main as main
