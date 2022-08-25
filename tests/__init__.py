import sys
from pathlib import Path

import pytest

sys.dangerzone_dev = True

SAMPLE_DIRECTORY = "test_docs"
BASIC_SAMPLE = "sample.pdf"
test_docs_dir = Path(__file__).parent.joinpath(SAMPLE_DIRECTORY)
test_docs = [
    p
    for p in test_docs_dir.rglob("*")
    if p.is_file() and not p.name.endswith("-safe.pdf")
]

# Pytest parameter decorators
for_each_doc = pytest.mark.parametrize("doc", test_docs)


class TestBase:
    sample_doc = str(test_docs_dir.joinpath(BASIC_SAMPLE))
