import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import List

import pytest

# Add src directory to Python path for imports
# src_dir = Path(__file__).parent.parent / "src"
# sys.path.insert(0, str(src_dir))

TESTS_DIRECTORY = Path(__file__).parent
SAFE_EXTENSION = "-safe.pdf"
TEST_DOCS_DIRECTORY = TESTS_DIRECTORY / "test_docs"

_DANGERZONE_SHARE_DIR = Path(__file__).parent / "share"


@pytest.fixture
def pdf_11k_pages(tmp_path: Path) -> str:
    """11K page document with pages of 1x1 px. Generated with the command:

    gs -sDEVICE=pdfwrite -o sample-11k-pages.pdf -dDEVICEWIDTHPOINTS=1 -dDEVICEHEIGHTPOINTS=1 -c 11000 {showpage} repeat
    """

    filename = "sample-11k-pages.pdf"
    zip_path = TEST_DOCS_DIRECTORY / f"{filename}.zip"
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(tmp_path)
    return str(tmp_path / filename)


test_docs = [
    p
    for p in TEST_DOCS_DIRECTORY.glob("*")
    if p.is_file()
    and not (
        p.name.endswith(SAFE_EXTENSION)
        or p.name.startswith("sample_bad")
        or ".pdf.zip" in p.name
    )
]

# Pytest parameter decorators
for_each_doc = pytest.mark.parametrize(
    "doc", test_docs, ids=[str(doc.name) for doc in test_docs]
)


@pytest.fixture
def bad_doc(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """Fixture for parametrized error tests.

    Accepts a Path/str to a document, or the string "pdf_11k_pages" to
    use the 11k-page fixture document (extracted from its zip on demand).
    """
    if request.param == "pdf_11k_pages":
        filename = "sample-11k-pages.pdf"
        zip_path = TEST_DOCS_DIRECTORY / f"{filename}.zip"
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            zip_file.extractall(tmp_path)
        return tmp_path / filename
    return Path(request.param)


def get_runtime_security_args() -> List[str]:
    """Return the security arguments for running the conversion container.

    Mirrors Container.get_runtime_security_args() defined in:
      dangerzone/isolation_provider/container.py

    Keep this function in sync with the upstream source of truth.
    """
    result = subprocess.run(
        ["podman", "version", "-f", "{{.Client.Version}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    major, minor, *_ = result.stdout.strip().split(".")
    runtime_version = (int(major), int(minor))

    if runtime_version < (4, 0):
        seccomp_path = _DANGERZONE_SHARE_DIR / "seccomp.gvisor.permissive.json"
    else:
        seccomp_path = _DANGERZONE_SHARE_DIR / "seccomp.gvisor.json"

    security_args = ["--log-driver", "none"]
    security_args += ["--security-opt", "no-new-privileges"]
    if runtime_version >= (4, 1):
        security_args += ["--userns", "nomap"]
    security_args += ["--security-opt", f"seccomp={seccomp_path}"]
    security_args += ["--cap-drop", "all"]
    security_args += ["--cap-add", "SYS_CHROOT"]
    security_args += ["--security-opt", "label=type:container_engine_t"]
    security_args += ["--network=none"]
    security_args += ["-u", "dangerzone"]

    return security_args


@pytest.fixture
def container_image(request: pytest.FixtureRequest) -> str:
    """Return the container image to use for container conversion tests."""
    image = (_DANGERZONE_SHARE_DIR / "image-id.txt").read_text().strip()
    if not image:
        image = request.config.getoption("--container-image")
    if not image:
        raise pytest.UsageError(
            "No container image available. Provide --container-image or populate "
            "tests/share/image-id.txt, or use --local."
        )
    return image


@pytest.fixture
def container_security_args() -> List[str]:
    """Return the security args for running the container, mirroring container.py."""
    try:
        return get_runtime_security_args()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        pytest.skip(f"Could not determine container security args: {e}")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-pixel-references",
        action="store_true",
        default=False,
        help=(
            "Regenerate reference pixel data (.bin files, gzip-compressed) using "
            "container conversion"
        ),
    )
    parser.addoption(
        "--container-image",
        default=None,
        help="Container image to use for container conversion tests",
    )
    parser.addoption(
        "--local",
        action="store_true",
        default=False,
        help="Run conversion tests locally instead of in a container",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--local") and config.getoption("--update-pixel-references"):
        raise pytest.UsageError(
            "--update-pixel-references must run in a container; do not combine with "
            "--local."
        )
    if not config.getoption("--local"):
        image = (_DANGERZONE_SHARE_DIR / "image-id.txt").read_text().strip()
        if not image and not config.getoption("--container-image"):
            raise pytest.UsageError(
                "No container image available. Provide --container-image or populate "
                "tests/share/image-id.txt, or use --local."
            )
