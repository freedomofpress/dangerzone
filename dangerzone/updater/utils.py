import subprocess

from . import errors


def ensure_cosign() -> None:
    try:
        subprocess.run(["cosign", "version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        raise errors.CosignNotInstalledError()
