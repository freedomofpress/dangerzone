import subprocess
from pathlib import Path

from ..container_utils import subprocess_run
from . import errors, log


def ensure_installed() -> None:
    try:
        subprocess_run(["cosign", "version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        raise errors.CosignNotInstalledError()


def verify_local_image(oci_image_folder: str, pubkey: Path) -> bool:
    """Verify the given path against the given public key"""

    ensure_installed()
    cmd = [
        "cosign",
        "verify",
        "--key",
        str(pubkey),
        "--offline",
        "--local-image",
        oci_image_folder,
    ]
    log.debug(" ".join(cmd))
    result = subprocess_run(cmd, capture_output=True)
    if result.returncode == 0:
        log.info("Signature verified")
        return True
    log.info("Failed to verify signature", result.stderr)
    return False
