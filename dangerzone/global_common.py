import subprocess
import gzip
from colorama import Fore, Back, Style

import dangerzone
import dangerzone.util as dzutil


def is_container_installed():
    """
    See if the podman container is installed. Linux only.
    """
    # Get the image id
    with open(dzutil.get_resource_path("image-id.txt")) as f:
        expected_image_id = f.read().strip()

    # See if this image is already installed
    installed = False
    found_image_id = subprocess.check_output(
        [
            dzutil.CONTAINER_RUNTIME,
            "image",
            "list",
            "--format",
            "{{.ID}}",
            dangerzone.util.CONTAINER_NAME,
        ],
        text=True,
        startupinfo=dzutil.get_subprocess_startupinfo(),
    )
    found_image_id = found_image_id.strip()

    if found_image_id == expected_image_id:
        installed = True
    elif found_image_id == "":
        pass
    else:
        print("Deleting old dangerzone container image")

        try:
            subprocess.check_output(
                [dzutil.CONTAINER_RUNTIME, "rmi", "--force", found_image_id],
                startupinfo=dzutil.get_subprocess_startupinfo(),
            )
        except:
            print("Couldn't delete old container image, so leaving it there")

    return installed


def install_container():
    """
    Make sure the podman container is installed. Linux only.
    """
    if is_container_installed():
        return

    # Load the container into podman
    print("Installing Dangerzone container image...")

    p = subprocess.Popen(
        [dzutil.CONTAINER_RUNTIME, "load"],
        stdin=subprocess.PIPE,
        startupinfo=dzutil.get_subprocess_startupinfo(),
    )

    chunk_size = 10240
    compressed_container_path = dzutil.get_resource_path("container.tar.gz")
    with gzip.open(compressed_container_path) as f:
        while True:
            chunk = f.read(chunk_size)
            if len(chunk) > 0:
                p.stdin.write(chunk)
            else:
                break
    p.communicate()

    if not is_container_installed():
        print("Failed to install the container image")
        return False

    print("Container image installed")
    return True


def display_banner():
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
    left_spaces = (15 - len(dzutil.VERSION) - 1) // 2
    right_spaces = left_spaces
    if left_spaces + len(dzutil.VERSION) + 1 + right_spaces < 15:
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
        + f"{' '*left_spaces}Dangerzone v{dzutil.VERSION}{' '*right_spaces}"
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
    print(Back.BLACK + Fore.YELLOW + Style.DIM + "╰──────────────────────────╯")
