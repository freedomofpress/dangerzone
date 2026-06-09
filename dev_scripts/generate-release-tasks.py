#!/usr/bin/env python3
import pathlib
import subprocess

RELEASE_DOCS_DIR = pathlib.Path("docs") / "developer" / "release"
DOCS = [
    "pre-release.md",
    "prepare-build-envs.md",
    "build.md",
    "qa.md",
    "release.md",
]


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
    first_pass = []
    second_pass = []

    with open(filename, "r") as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip()
        if line.startswith("#") or line.lstrip().startswith("- [ ]"):
            first_pass.append(line)

    current_level = 0
    for line in reversed(first_pass):
        level = len(line) - len(line.lstrip("#"))
        if (level >= current_level > 0) or (level > 0 and not second_pass):
            continue
        current_level = level
        second_pass.append(line)

    return "\n".join(reversed(second_pass))


if __name__ == "__main__":
    for name in DOCS:
        path = git_root() / RELEASE_DOCS_DIR / name
        print(extract_checkboxes(path))
