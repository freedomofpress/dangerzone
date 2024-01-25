import platform
import subprocess
from pathlib import Path

import pytest

from dangerzone.isolation_provider.container import Container
from dangerzone.logic import DangerzoneCore


# TODO: Perform an equivalent test on Qubes.
# NOTE: We skip running this test on Windows/MacOS, because our current CI cannot run
# Docker in these platforms. It's not a problem anyways, because the result should be
# the same in all container-based platforms.
@pytest.mark.skipif(platform.system() != "Linux", reason="Container-specific")
def test_ocr_ommisions() -> None:
    # Create the command that will list all the installed languages in the container
    # image.
    runtime = Container.get_runtime()
    command = [
        runtime,
        "run",
        Container.CONTAINER_NAME,
        "find",
        "/usr/share/tessdata/",
        "-name",
        "*.traineddata",
    ]

    # Run the command, strip any extra whitespace, and remove the following first line
    # from the result:
    #
    #     List of available languages in "/usr/share/tessdata/" ...
    installed_langs_filenames = (
        subprocess.run(command, text=True, check=True, stdout=subprocess.PIPE)
        .stdout.strip()
        .split("\n")
    )
    installed_langs = set(
        [
            Path(filename).name.split(".traineddata")[0]
            for filename in installed_langs_filenames
        ]
    )

    # Remove the "osd" and "equ" languages from the list of installed languages, since
    # they are not an actual language. Read more in:
    # https://pyimagesearch.com/2021/11/15/tesseract-page-segmentation-modes-psms-explained-how-to-improve-your-ocr-accuracy/
    installed_langs -= {"osd", "equ"}

    # Grab the languages that Dangerzone offers to the user through the GUI/CLI.
    offered_langs = set(DangerzoneCore(Container()).ocr_languages.values())

    # Ensure that both the installed languages and the ones we offer to the user are the
    # same.
    assert installed_langs == offered_langs
