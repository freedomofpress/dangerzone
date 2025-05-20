import subprocess
from pathlib import Path

from ..container_utils import subprocess_run
from ..util import get_resource_path
from . import errors, log

_COSIGN_BINARY = str(get_resource_path("vendor/cosign").absolute())


def verify_local_image(oci_image_folder: str, pubkey: Path) -> bool:
    """Verify the given path against the given public key"""
    cmd = [
        _COSIGN_BINARY,
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


def verify_blob(pubkey: Path, bundle: str, payload: str) -> bool:
    cmd = [
        _COSIGN_BINARY,
        "verify-blob",
        "--key",
        str(pubkey.absolute()),
        "--bundle",
        bundle,
        payload,
    ]
    log.debug(" ".join(cmd))
    result = subprocess_run(cmd, capture_output=True)
    # If the process return code is not 0, or doesn't contain the expected
    # string, we raise an error.
    if result.returncode != 0 or result.stderr != b"Verified OK\n":
        log.debug("Failed to verify signature", result.stderr)
        raise errors.SignatureVerificationError("Failed to verify signature")
    log.debug("Signature verified")
    return True


def download_signature(image: str, digest: str) -> list[str]:
    try:
        process = subprocess_run(
            [
                _COSIGN_BINARY,
                "download",
                "signature",
                f"{image}@sha256:{digest}",
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.NoRemoteSignatures(e)

    # Remove the last return, split on newlines, convert from JSON
    return process.stdout.decode("utf-8").strip().split("\n")  # type:ignore[attr-defined]


def save(arch_image: str, destination: Path):
    process = subprocess_run(
        [_COSIGN_BINARY, "save", arch_image, "--dir", str(destination.absolute())],
        capture_output=True,
        check=True,
    )
    if process.returncode != 0:
        raise errors.AirgappedImageDownloadError()
