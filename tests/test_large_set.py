import os
import re
import subprocess
import time
from pathlib import Path
from typing import List

import pytest
from _pytest.fixtures import FixtureRequest

from dangerzone.document import SAFE_EXTENSION

from .test_cli import TestCli

test_docs_repo_dir = Path(__file__).parent / "test_docs_large"
test_docs_dir = test_docs_repo_dir / "all_documents"
TEST_DOCS_REPO = "git@github.com:freedomofpress/dangerzone-test-set.git"
FORMATS_REGEX = (
    r".*\.(pdf|docx|doc|xlsx|xls|pptx|ppt|odt|ods|odp|odg|jpg|jpeg|gif|png)$"
)


def ensure_test_data_exists() -> None:
    if len(os.listdir(test_docs_repo_dir)) == 0:
        print("Test data repository it empty. Skipping large tests.")
        exit(1)


def get_test_docs(min_size: int, max_size: int) -> List[Path]:
    ensure_test_data_exists()
    return sorted(
        [
            doc
            for doc in test_docs_dir.rglob("*")
            if doc.is_file()
            and min_size < doc.stat().st_size < max_size
            and not (doc.name.endswith(SAFE_EXTENSION))
            and re.match(FORMATS_REGEX, doc.name)
        ]
    )


docs_10K = get_test_docs(min_size=0, max_size=10 * 2**10)

# Pytest parameter decorators
for_each_10K_doc = pytest.mark.parametrize(
    "doc", docs_10K, ids=[str(doc.name) for doc in docs_10K]
)


class TestLargeSet(TestCli):
    def run_doc_test(self, doc: Path, tmp_path: Path) -> None:
        output_file_path = str(tmp_path / "output.pdf")
        p = subprocess.Popen(
            [
                "python",
                "dev_scripts/dangerzone-cli",
                "--output-filename",
                output_file_path,
                "--ocr-lang",
                "eng",
                str(doc),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out, _ = p.communicate()
        from strip_ansi import strip_ansi

        print(strip_ansi(out.decode()))
        assert p.returncode == 0

    @for_each_10K_doc
    def test_10K_docs(self, doc: Path, tmp_path: Path) -> None:
        self.run_doc_test(doc, tmp_path)
