import re
import subprocess
import tempfile
from pathlib import Path

import click

DOC_TO_PIXELS_LOG_START = "----- DOC TO PIXELS LOG START -----"
DOC_TO_PIXELS_LOG_END = "----- DOC TO PIXELS LOG END -----"

report_tool_path = str(Path(__file__).parent / "report.sh")

import xml.etree.ElementTree as ET
from typing import List


class TestResult:
    def __init__(self, test_name: str, system_out: str, failure: str = None) -> None:
        self.test_name = test_name
        self.system_out = system_out
        self.failure = failure

    def get_doc_to_pixels_log(self) -> str:
        return self._get_log(DOC_TO_PIXELS_LOG_START, DOC_TO_PIXELS_LOG_END)

    def _get_log(self, armor_start: str, armor_end: str) -> str:
        if armor_start not in self.system_out:
            return ""
        else:
            (_, log) = self.system_out.split(armor_start)
            (log, _) = log.split(armor_end)
            return log


def parse_test_results(report_path: str) -> List[TestResult]:
    with open(report_path, "r") as xml_file:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        for testcase in root.iter("testcase"):
            if testcase.find("failure") is not None:
                failure_text = testcase.find("failure").text
            else:
                failure_text = None
            yield TestResult(
                test_name=testcase.get("name"),
                system_out=testcase.find("system-out").text,
                failure=failure_text,
            )


def summarize_results(report: str) -> None:
    print("==== RESULTS SUMMARY ===")
    with open(report, "r") as r:
        first_line = r.readline()
        second_line = r.readline()
        match_stats = re.match(
            r'.*errors="(\d+)" failures="(\d+)" skipped="(\d+)" tests="(\d+)"',
            first_line.strip() + second_line,
        )  #
        print(
            f"""
    errors: {match_stats.group(1)}
    failures: {match_stats.group(2)}
    skipped: {match_stats.group(3)}
    tests: {match_stats.group(4)}
    failure rate: {(int(match_stats.group(1)) + int(match_stats.group(2))) / int(match_stats.group(4))}
        """
        )


def get_failure_reasons(report: str) -> str:
    pass


@click.command()
@click.argument(
    "report",
    required=True,
    nargs=1,
)
def main(report: str):
    summarize_results(report)
    with tempfile.NamedTemporaryFile("w") as failure_report:
        test_reports = parse_test_results(report)
        failures = [t for t in test_reports if t.failure]
        for failure in failures:
            failure_report.write(failure.get_doc_to_pixels_log())
        failure_report.flush()

        with tempfile.NamedTemporaryFile("w") as temp_report:
            test_reports = parse_test_results(report)
            for test in test_reports:
                temp_report.write(test.get_doc_to_pixels_log())
            temp_report.flush()
            print(
                subprocess.check_output(
                    [
                        "bash",
                        report_tool_path,
                        str(temp_report.name),
                        str(failure_report.name),
                    ],
                    universal_newlines=True,
                )
            )


if __name__ == "__main__":
    main()
