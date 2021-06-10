import os
import sys
import colorama

colorama.init(autoreset=True)

# Depending on the filename, decide if we want to run:
# dangerzone, dangerzone-cli, or dangerzone-container

basename = os.path.basename(sys.argv[0])

if basename == "dangerzone-container" or basename == "dangerzone-container.exe":
    from .container import container_main as main
elif basename == "dangerzone-cli" or basename == "dangerzone-cli.exe":
    from .cli import cli_main as main
else:
    from .gui import gui_main as main
