import sys
from pathlib import Path
from typing import Callable, List

import pytest

from dangerzone.document import SAFE_EXTENSION

sys.dangerzone_dev = True  # type: ignore[attr-defined]


SAMPLE_DIRECTORY = "test_docs"
BASIC_SAMPLE_PDF = "sample-pdf.pdf"
BASIC_SAMPLE_DOC = "sample-doc.doc"
SAMPLE_EXTERNAL_DIRECTORY = "test_docs_external"
test_docs_dir = Path(__file__).parent.joinpath(SAMPLE_DIRECTORY)
test_docs = [
    p
    for p in test_docs_dir.rglob("*")
    if p.is_file()
    and not (p.name.endswith(SAFE_EXTENSION) or p.name.startswith("sample_bad"))
]

# Pytest parameter decorators
for_each_doc = pytest.mark.parametrize(
    "doc", test_docs, ids=[str(doc.name) for doc in test_docs]
)


@pytest.fixture
def sample_pdf() -> str:
    return str(test_docs_dir.joinpath(BASIC_SAMPLE_PDF))


# External Docs - base64 docs encoded for externally sourced documents
# XXX to reduce the chance of accidentally opening them
test_docs_external_dir = Path(__file__).parent.joinpath(SAMPLE_EXTERNAL_DIRECTORY)


@pytest.fixture
def sample_doc() -> str:
    return str(test_docs_dir.joinpath(BASIC_SAMPLE_DOC))


def get_docs_external(pattern: str = "*") -> List[Path]:
    if not pattern.endswith("*"):
        pattern = f"{pattern}.b64"
    return [
        p
        for p in test_docs_external_dir.rglob(pattern)
        if p.is_file() and not (p.name.endswith(SAFE_EXTENSION))
    ]


# Pytest parameter decorators
def for_each_external_doc(glob_pattern: str = "*") -> Callable:
    test_docs_external = get_docs_external(glob_pattern)
    return pytest.mark.parametrize(
        "doc",
        test_docs_external,
        ids=[str(doc.name).rstrip(".b64") for doc in test_docs_external],
    )


class TestBase:
    sample_doc = str(test_docs_dir.joinpath(BASIC_SAMPLE_PDF))


@pytest.fixture
def unreadable_pdf(tmp_path: Path) -> str:
    file_path = tmp_path / "document.pdf"
    file_path.touch(mode=0o000)
    return str(file_path)


@pytest.fixture
def uncommon_text() -> str:
    """Craft a string with Unicode characters that are considered not common.

    Create a string that contains the following uncommon characters:

    * ANSI escape sequences: \033[31;1;4m and \033[0m
    * A Unicode character that resembles an English character: greek "X" (U+03A7)
    * A Unicode control character that is not part of ASCII: zero-width joiner
      (U+200D)
    * An emoji: Cross Mark (U+274C)
    """
    return "\033[31;1;4m BaD TeΧt \u200d ❌ \033[0m"


@pytest.fixture
def sanitized_text() -> str:
    """Return a sanitized version of the uncommon_text."""
    return "_[31;1;4m BaD Te_t _ _ _[0m"
