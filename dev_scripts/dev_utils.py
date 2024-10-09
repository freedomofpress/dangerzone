import pathlib
import subprocess


def git_root():
    """Get the root directory of the Git repo."""
    # FIXME: Use a Git Python binding for this.
    # FIXME: Make this work if called outside the repo.
    path = (
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
        .decode()
        .strip("\n")
    )
    return pathlib.Path(path)
