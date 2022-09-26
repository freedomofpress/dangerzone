import gzip
import json
import logging
import os
import pipes
import platform
import shutil
import subprocess
import tempfile
from typing import Callable, List, Optional, Tuple

import appdirs
from colorama import Fore, Style

from .document import Document
from .util import get_resource_path, get_subprocess_startupinfo

container_name = "dangerzone.rocks/dangerzone"

# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()  # type: ignore [attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore [attr-defined]
else:
    startupinfo = None

log = logging.getLogger(__name__)

# Name of the dangerzone container
container_name = "dangerzone.rocks/dangerzone"


class NoContainerTechException(Exception):
    def __init__(self, container_tech: str) -> None:
        super().__init__(f"{container_tech} is not installed")


def get_runtime_name() -> str:
    if platform.system() == "Linux":
        runtime_name = "podman"
    else:
        # Windows, Darwin, and unknown use docker for now, dangerzone-vm eventually
        runtime_name = "docker"
    return runtime_name


def get_runtime() -> str:
    container_tech = get_runtime_name()
    runtime = shutil.which(container_tech)
    if runtime is None:
        raise NoContainerTechException(container_tech)
    return runtime


def install() -> bool:
    """
    Make sure the podman container is installed. Linux only.
    """
    if is_container_installed():
        return True

    # Load the container into podman
    log.info("Installing Dangerzone container image...")

    p = subprocess.Popen(
        [get_runtime(), "load"],
        stdin=subprocess.PIPE,
        startupinfo=get_subprocess_startupinfo(),
    )

    chunk_size = 10240
    compressed_container_path = get_resource_path("container.tar.gz")
    with gzip.open(compressed_container_path) as f:
        while True:
            chunk = f.read(chunk_size)
            if len(chunk) > 0:
                if p.stdin:
                    p.stdin.write(chunk)
            else:
                break
    p.communicate()

    if not is_container_installed():
        log.error("Failed to install the container image")
        return False

    log.info("Container image installed")
    return True


def is_container_installed() -> bool:
    """
    See if the podman container is installed. Linux only.
    """
    # Get the image id
    with open(get_resource_path("image-id.txt")) as f:
        expected_image_id = f.read().strip()

    # See if this image is already installed
    installed = False
    found_image_id = subprocess.check_output(
        [
            get_runtime(),
            "image",
            "list",
            "--format",
            "{{.ID}}",
            container_name,
        ],
        text=True,
        startupinfo=get_subprocess_startupinfo(),
    )
    found_image_id = found_image_id.strip()

    if found_image_id == expected_image_id:
        installed = True
    elif found_image_id == "":
        pass
    else:
        log.info("Deleting old dangerzone container image")

        try:
            subprocess.check_output(
                [get_runtime(), "rmi", "--force", found_image_id],
                startupinfo=get_subprocess_startupinfo(),
            )
        except:
            log.warning("Couldn't delete old container image, so leaving it there")

    return installed


def parse_progress(document: Document, line: str) -> Tuple[bool, str, int]:
    """
    Parses a line returned by the container.
    """
    try:
        status = json.loads(line)
    except:
        error_message = f"Invalid JSON returned from container:\n\n\t {line}"
        log.error(error_message)
        return (True, error_message, -1)

    s = Style.BRIGHT + Fore.YELLOW + f"[doc {document.id}] "
    s += Fore.CYAN + f"{status['percentage']}% "
    if status["error"]:
        s += Style.RESET_ALL + Fore.RED + status["text"]
        log.error(s)
    else:
        s += Style.RESET_ALL + status["text"]
        log.info(s)

    return (status["error"], status["text"], status["percentage"])


def exec(
    document: Document,
    args: List[str],
    stdout_callback: Optional[Callable] = None,
) -> int:
    args_str = " ".join(pipes.quote(s) for s in args)
    log.info("> " + args_str)

    with subprocess.Popen(
        args,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        startupinfo=startupinfo,
    ) as p:
        if p.stdout is not None:
            for line in p.stdout:
                (error, text, percentage) = parse_progress(document, line)
                if stdout_callback:
                    stdout_callback(error, text, percentage)

        p.communicate()
        return p.returncode


def exec_container(
    document: Document,
    command: List[str],
    extra_args: List[str] = [],
    stdout_callback: Optional[Callable] = None,
) -> int:
    container_runtime = get_runtime()

    if get_runtime_name() == "podman":
        platform_args = []
        security_args = ["--security-opt", "no-new-privileges"]
        security_args += ["--userns", "keep-id"]
    else:
        platform_args = ["--platform", "linux/amd64"]
        security_args = ["--security-opt=no-new-privileges:true"]

    # drop all linux kernel capabilities
    security_args += ["--cap-drop", "all"]
    user_args = ["-u", "dangerzone"]

    prevent_leakage_args = ["--rm"]

    args = (
        ["run", "--network", "none"]
        + platform_args
        + user_args
        + security_args
        + prevent_leakage_args
        + extra_args
        + [container_name]
        + command
    )

    args = [container_runtime] + args
    return exec(document, args, stdout_callback)


def convert(
    document: Document,
    ocr_lang: Optional[str],
    stdout_callback: Optional[Callable] = None,
) -> bool:
    success = False

    if ocr_lang:
        ocr = "1"
    else:
        ocr = "0"

    dz_tmp = os.path.join(appdirs.user_config_dir("dangerzone"), "tmp")
    os.makedirs(dz_tmp, exist_ok=True)

    tmpdir = tempfile.TemporaryDirectory(dir=dz_tmp)
    pixel_dir = os.path.join(tmpdir.name, "pixels")
    safe_dir = os.path.join(tmpdir.name, "safe")
    os.makedirs(pixel_dir, exist_ok=True)
    os.makedirs(safe_dir, exist_ok=True)

    # Convert document to pixels
    command = ["/usr/bin/python3", "/usr/local/bin/dangerzone.py", "document-to-pixels"]
    extra_args = [
        "-v",
        f"{document.input_filename}:/tmp/input_file",
        "-v",
        f"{pixel_dir}:/dangerzone",
    ]
    ret = exec_container(document, command, extra_args, stdout_callback)
    if ret != 0:
        log.error("documents-to-pixels failed")
    else:
        # TODO: validate convert to pixels output

        # Convert pixels to safe PDF
        command = ["/usr/bin/python3", "/usr/local/bin/dangerzone.py", "pixels-to-pdf"]
        extra_args = [
            "-v",
            f"{pixel_dir}:/dangerzone",
            "-v",
            f"{safe_dir}:/safezone",
            "-e",
            f"OCR={ocr}",
            "-e",
            f"OCR_LANGUAGE={ocr_lang}",
        ]
        ret = exec_container(document, command, extra_args, stdout_callback)
        if ret != 0:
            log.error("pixels-to-pdf failed")
        else:
            # Move the final file to the right place
            if os.path.exists(document.output_filename):
                os.remove(document.output_filename)

            container_output_filename = os.path.join(
                safe_dir, "safe-output-compressed.pdf"
            )
            shutil.move(container_output_filename, document.output_filename)

            # We did it
            success = True

    # Clean up
    tmpdir.cleanup()

    return success


def get_max_parallel_conversions() -> int:
    n_cpu = 1
    if platform.system() == "Linux":
        # if on linux containers run natively
        cpu_count = os.cpu_count()
        if cpu_count is not None:
            n_cpu = cpu_count

    elif get_runtime_name() == "docker":
        # For Windows and MacOS containers run in VM
        # So we obtain the CPU count for the VM
        n_cpu_str = subprocess.check_output(
            [get_runtime(), "info", "--format", "{{.NCPU}}"],
            text=True,
            startupinfo=get_subprocess_startupinfo(),
        )
        n_cpu = int(n_cpu_str.strip())

    return 2 * n_cpu + 1


# From global_common:

# def validate_convert_to_pixel_output(self, common, output):
#     """
#     Take the output from the convert to pixels tasks and validate it. Returns
#     a tuple like: (success (boolean), error_message (str))
#     """
#     max_image_width = 10000
#     max_image_height = 10000

#     # Did we hit an error?
#     for line in output.split("\n"):
#         if (
#             "failed:" in line
#             or "The document format is not supported" in line
#             or "Error" in line
#         ):
#             return False, output

#     # How many pages was that?
#     num_pages = None
#     for line in output.split("\n"):
#         if line.startswith("Document has "):
#             num_pages = line.split(" ")[2]
#             break
#     if not num_pages or not num_pages.isdigit() or int(num_pages) <= 0:
#         return False, "Invalid number of pages returned"
#     num_pages = int(num_pages)

#     # Make sure we have the files we expect
#     expected_filenames = []
#     for i in range(1, num_pages + 1):
#         expected_filenames += [
#             f"page-{i}.rgb",
#             f"page-{i}.width",
#             f"page-{i}.height",
#         ]
#     expected_filenames.sort()
#     actual_filenames = os.listdir(common.pixel_dir.name)
#     actual_filenames.sort()

#     if expected_filenames != actual_filenames:
#         return (
#             False,
#             f"We expected these files:\n{expected_filenames}\n\nBut we got these files:\n{actual_filenames}",
#         )

#     # Make sure the files are the correct sizes
#     for i in range(1, num_pages + 1):
#         with open(f"{common.pixel_dir.name}/page-{i}.width") as f:
#             w_str = f.read().strip()
#         with open(f"{common.pixel_dir.name}/page-{i}.height") as f:
#             h_str = f.read().strip()
#         w = int(w_str)
#         h = int(h_str)
#         if (
#             not w_str.isdigit()
#             or not h_str.isdigit()
#             or w <= 0
#             or w > max_image_width
#             or h <= 0
#             or h > max_image_height
#         ):
#             return False, f"Page {i} has invalid geometry"

#         # Make sure the RGB file is the correct size
#         if os.path.getsize(f"{common.pixel_dir.name}/page-{i}.rgb") != w * h * 3:
#             return False, f"Page {i} has an invalid RGB file size"

#     return True, True
