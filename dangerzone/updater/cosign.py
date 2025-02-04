import subprocess

from . import errors, log


def ensure_installed() -> None:
    try:
        subprocess.run(["cosign", "version"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        raise errors.CosignNotInstalledError()


def verify_local_image(oci_image_folder: str, pubkey: str) -> bool:
    """Verify the given path against the given public key"""

    ensure_installed()
    cmd = [
        "cosign",
        "verify",
        "--key",
        pubkey,
        "--offline",
        "--local-image",
        oci_image_folder,
    ]
    log.debug(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        log.debug("Signature verified")
        return True
    log.debug("Failed to verify signature", result.stderr)
    return False
