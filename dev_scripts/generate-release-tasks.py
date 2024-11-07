#!/usr/bin/env python3
import pathlib
import subprocess

RELEASE_FILE = "RELEASE.md"
QA_FILE = "QA.md"


def git_root():
    """Get the root directory of the Git repo."""
    # FIXME: Use a Git Python binding for this.
    # FIXME: Make this work if called outside the repo.
    path = (
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
        )
        .stdout.decode()
        .strip("\n")
    )
    return pathlib.Path(path)


def extract_checkboxes(filename):
    headers = []
    result = []

    with open(filename, "r") as f:
        lines = f.readlines()

    current_level = 0
    for line in lines:
        line = line.rstrip()

        # If it's a header, store it
        if line.startswith("#"):
            # Count number of # to determine header level
            level = len(line) - len(line.lstrip("#"))
            if level < current_level or not current_level:
                headers.extend(["", line, ""])
                current_level = level
            elif level > current_level:
                continue
            else:
                headers = ["", line, ""]

        # If it's a checkbox
        elif "- [ ]" in line or "- [x]" in line or "- [X]" in line:
            # Print the last header if we haven't already
            if headers:
                result.extend(headers)
                headers = []
                current_level = 0

            # If this is the "Do the QA tasks" line, recursively get QA tasks
            if "Do the QA tasks" in line:
                result.append(line)
                qa_tasks = extract_checkboxes(git_root() / QA_FILE)
                result.append(qa_tasks)
            else:
                result.append(line)
    return "\n".join(result)


if __name__ == "__main__":
    print(extract_checkboxes(git_root() / RELEASE_FILE))
