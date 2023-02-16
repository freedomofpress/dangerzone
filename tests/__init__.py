import sys
from pathlib import Path

import pytest

sys.dangerzone_dev = True  # type: ignore[attr-defined]

from dangerzone.document import SAFE_EXTENSION

SAMPLE_DIRECTORY = "test_docs"
BASIC_SAMPLE = "sample-pdf.pdf"
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


class TestBase:
    sample_doc = str(test_docs_dir.joinpath(BASIC_SAMPLE))


@pytest.fixture
def sample_doc() -> str:
    return str(test_docs_dir.joinpath(BASIC_SAMPLE))


@pytest.fixture
def unreadable_pdf(tmp_path: Path) -> str:
    file_path = tmp_path / "document.pdf"
    file_path.touch(mode=0o000)
    return str(file_path)
