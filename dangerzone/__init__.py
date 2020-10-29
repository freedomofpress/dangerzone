import os
import sys
from .container import container_main

dangerzone_version = "0.1.4"

# This is a hack for Windows and Mac to be able to run dangerzone-container, even though
# PyInstaller builds a single binary
basename = os.path.basename(sys.argv[0])
if basename == "dangerzone-container" or basename == "dangerzone-container.exe":
    main = container_main
else:
    # If the binary isn't "dangerzone-contatiner", then launch the GUI
    from .gui import gui_main as main
