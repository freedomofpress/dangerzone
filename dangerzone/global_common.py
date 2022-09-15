import gzip
import json
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
from typing import Optional

import appdirs
import colorama

from .container import convert
from .settings import Settings
from .util import get_resource_path, get_subprocess_startupinfo

log = logging.getLogger(__name__)


class GlobalCommon(object):
    """
    The GlobalCommon class is a singleton of shared functionality throughout the app
    """

    def __init__(self) -> None:
        # Initialize terminal colors
        colorama.init(autoreset=True)

        # App data folder
        self.appdata_path = appdirs.user_config_dir("dangerzone")

        # Container
        self.container_name = "dangerzone.rocks/dangerzone"

        # Languages supported by tesseract
        with open(get_resource_path("ocr-languages.json"), "r") as f:
            self.ocr_languages = json.load(f)

        # Load settings
        self.settings = Settings(self)

    def get_container_runtime(self) -> str:
        if platform.system() == "Linux":
            runtime_name = "podman"
        else:
            runtime_name = "docker"
        runtime = shutil.which(runtime_name)
        if runtime is None:
            raise Exception(f"{runtime_name} is not installed")
        return runtime

    def install_container(self) -> Optional[bool]:
        """
        Make sure the podman container is installed. Linux only.
        """
        if self.is_container_installed():
            return True

        # Load the container into podman
        log.info("Installing Dangerzone container image...")

        p = subprocess.Popen(
            [self.get_container_runtime(), "load"],
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

        if not self.is_container_installed():
            log.error("Failed to install the container image")
            return False

        log.info("Container image installed")
        return True

    def is_container_installed(self) -> bool:
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
                self.get_container_runtime(),
                "image",
                "list",
                "--format",
                "{{.ID}}",
                self.container_name,
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
                    [self.get_container_runtime(), "rmi", "--force", found_image_id],
                    startupinfo=get_subprocess_startupinfo(),
                )
            except:
                log.warning("Couldn't delete old container image, so leaving it there")

        return installed
