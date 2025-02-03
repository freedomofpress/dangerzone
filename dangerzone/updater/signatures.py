import json
import platform
import re
import subprocess
import tarfile
from base64 import b64decode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Dict, List, Optional, Tuple

from .. import container_utils as runtime
from . import errors, log, registry, utils

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs  # type: ignore[no-redef]


def get_config_dir() -> Path:
    return Path(platformdirs.user_config_dir("dangerzone"))


# XXX Store this somewhere else.
SIGNATURES_PATH = get_config_dir() / "signatures"
__all__ = [
    "verify_signature",
    "load_signatures",
    "store_signatures",
    "verify_offline_image_signature",
]


def signature_to_bundle(sig: Dict) -> Dict:
    """Convert a cosign-download signature to the format expected by cosign bundle."""
    bundle = sig["Bundle"]
    payload = bundle["Payload"]
    return {
        "base64Signature": sig["Base64Signature"],
        "Payload": sig["Payload"],
        "cert": sig["Cert"],
        "chain": sig["Chain"],
        "rekorBundle": {
            "SignedEntryTimestamp": bundle["SignedEntryTimestamp"],
            "Payload": {
                "body": payload["body"],
                "integratedTime": payload["integratedTime"],
                "logIndex": payload["logIndex"],
                "logID": payload["logID"],
            },
        },
        "RFC3161Timestamp": sig["RFC3161Timestamp"],
    }


def cosign_verify_local_image(oci_image_folder: str, pubkey: str) -> bool:
    """Verify the given path against the given public key"""

    utils.ensure_cosign()
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


def verify_signature(signature: dict, image_hash: str, pubkey: str) -> bool:
    """Verify a signature against a given public key"""
    # XXX - Also verfy the identity/docker-reference field against the expected value
    # e.g. ghcr.io/freedomofpress/dangerzone/dangerzone

    utils.ensure_cosign()
    signature_bundle = signature_to_bundle(signature)

    payload_bytes = b64decode(signature_bundle["Payload"])
    if json.loads(payload_bytes)["critical"]["type"] != f"sha256:{image_hash}":
        raise errors.SignatureMismatch("The signature does not match the image hash")

    with (
        NamedTemporaryFile(mode="w") as signature_file,
        NamedTemporaryFile(mode="bw") as payload_file,
    ):
        json.dump(signature_bundle, signature_file)
        signature_file.flush()

        payload_file.write(payload_bytes)
        payload_file.flush()

        cmd = [
            "cosign",
            "verify-blob",
            "--key",
            pubkey,
            "--bundle",
            signature_file.name,
            payload_file.name,
        ]
        log.debug(" ".join(cmd))
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # XXX Raise instead?
            log.debug("Failed to verify signature", result.stderr)
            return False
        if result.stderr == b"Verified OK\n":
            log.debug("Signature verified")
            return True
    return False


def new_image_release(image: str) -> bool:
    remote_hash = registry.get_manifest_hash(image)
    local_hash = runtime.get_local_image_hash(image)
    log.debug("Remote hash: %s", remote_hash)
    log.debug("Local hash: %s", local_hash)
    return remote_hash != local_hash


def verify_signatures(
    signatures: List[Dict],
    image_hash: str,
    pubkey: str,
) -> bool:
    for signature in signatures:
        if not verify_signature(signature, image_hash, pubkey):
            raise errors.SignatureVerificationError()
    return True


def upgrade_container_image(image: str, manifest_hash: str, pubkey: str) -> bool:
    """Verify and upgrade the image to the latest, if signed."""
    if not new_image_release(image):
        raise errors.ImageAlreadyUpToDate("The image is already up to date")

    signatures = get_remote_signatures(image, manifest_hash)
    verify_signatures(signatures, manifest_hash, pubkey)

    # At this point, the signatures are verified
    # We store the signatures just now to avoid storing unverified signatures
    store_signatures(signatures, manifest_hash, pubkey)

    # let's upgrade the image
    # XXX Use the image digest here to avoid race conditions
    return runtime.container_pull(image)


def upgrade_container_image_airgapped(
    container_tar: str, pubkey: str, image_name: str
) -> bool:
    """
    Verify the given archive against its self-contained signatures, then
    upgrade the image and retag it to the expected tag.

    Right now, the archive is extracted and reconstructed, requiring some space
    on the filesystem.
    """
    # XXX Use a memory buffer instead of the filesystem
    with TemporaryDirectory() as tmpdir:
        with tarfile.open(container_tar, "r") as archive:
            archive.extractall(tmpdir)

        # XXX Check if the contained signatures match the given ones?
        # Or maybe store both signatures?
        if not cosign_verify_local_image(tmpdir, pubkey):
            raise errors.SignatureVerificationError()

        # Remove the signatures from the archive.
        with open(Path(tmpdir) / "index.json") as f:
            index_json = json.load(f)
            index_json["manifests"] = [
                manifest
                for manifest in index_json["manifests"]
                if manifest["annotations"].get("kind")
                != "dev.cosignproject.cosign/sigs"
            ]

        image_digest = index_json["manifests"][0].get("digest")

        # Write the new index.json to the temp folder
        with open(Path(tmpdir) / "index.json", "w") as f:
            json.dump(index_json, f)

        with NamedTemporaryFile(suffix=".tar") as temporary_tar:
            with tarfile.open(temporary_tar.name, "w") as archive:
                # The root is the tmpdir
                archive.add(Path(tmpdir) / "index.json", arcname="index.json")
                archive.add(Path(tmpdir) / "oci-layout", arcname="oci-layout")
                archive.add(Path(tmpdir) / "blobs", arcname="blobs")

            runtime.load_image_tarball_file(temporary_tar.name)
            runtime.tag_image_by_digest(image_digest, image_name)

    # XXX Convert the signatures to the expected format

    # At this point, the signatures are verified
    # We store the signatures just now to avoid storing unverified signatures
    # store_signatures(signatures, image_hash, pubkey)

    return True


def get_file_hash(file: Optional[str] = None, content: Optional[bytes] = None) -> str:
    """Get the sha256 hash of a file or content"""
    if not file and not content:
        raise errors.UpdaterError("No file or content provided")
    if file:
        with open(file, "rb") as f:
            content = f.read()
    if content:
        return sha256(content).hexdigest()
    return ""


def load_signatures(image_hash: str, pubkey: str) -> List[Dict]:
    """
    Load signatures from the local filesystem

    See store_signatures() for the expected format.
    """
    pubkey_signatures = SIGNATURES_PATH / get_file_hash(pubkey)
    if not pubkey_signatures.exists():
        msg = (
            f"Cannot find a '{pubkey_signatures}' folder."
            "You might need to download the image signatures first."
        )
        raise errors.SignaturesFolderDoesNotExist(msg)

    with open(pubkey_signatures / f"{image_hash}.json") as f:
        log.debug("Loading signatures from %s", f.name)
        return json.load(f)


def store_signatures(signatures: list[Dict], image_hash: str, pubkey: str) -> None:
    """
    Store signatures locally in the SIGNATURE_PATH folder, like this:

    ~/.config/dangerzone/signatures/
    └── <pubkey-hash>
        └── <image-hash>.json
        └── <image-hash>.json

    The format used in the `.json` file is the one of `cosign download
    signature`, which differs from the "bundle" one used afterwards.

    It can be converted to the one expected by cosign verify --bundle with
    the `signature_to_bundle()` function.
    """

    def _get_digest(sig: Dict) -> str:
        payload = json.loads(b64decode(sig["Payload"]))
        return payload["critical"]["image"]["docker-manifest-digest"]

    # All the signatures should share the same hash.
    hashes = list(map(_get_digest, signatures))
    if len(set(hashes)) != 1:
        raise errors.InvalidSignatures("Signatures do not share the same image hash")

    if f"sha256:{image_hash}" != hashes[0]:
        raise errors.SignatureMismatch("Signatures do not match the given image hash")

    pubkey_signatures = SIGNATURES_PATH / get_file_hash(pubkey)
    pubkey_signatures.mkdir(exist_ok=True)

    with open(pubkey_signatures / f"{image_hash}.json", "w") as f:
        log.debug(
            f"Storing signatures for {image_hash} in {pubkey_signatures}/{image_hash}.json"
        )
        json.dump(signatures, f)


def verify_offline_image_signature(image: str, pubkey: str) -> bool:
    """
    Verifies that a local image has a valid signature
    """
    log.info(f"Verifying local image {image} against pubkey {pubkey}")
    image_hash = runtime.get_local_image_hash(image)
    log.debug(f"Image hash: {image_hash}")
    signatures = load_signatures(image_hash, pubkey)
    if len(signatures) < 1:
        raise errors.LocalSignatureNotFound("No signatures found")

    for signature in signatures:
        if not verify_signature(signature, image_hash, pubkey):
            msg = f"Unable to verify signature for {image} with pubkey {pubkey}"
            raise errors.SignatureVerificationError(msg)
    return True


def get_remote_signatures(image: str, hash: str) -> List[Dict]:
    """Retrieve the signatures from the registry, via `cosign download`."""
    utils.ensure_cosign()

    process = subprocess.run(
        ["cosign", "download", "signature", f"{image}@sha256:{hash}"],
        capture_output=True,
        check=True,
    )

    # XXX: Check the output first.
    # Remove the last return, split on newlines, convert from JSON
    signatures_raw = process.stdout.decode("utf-8").strip().split("\n")
    signatures = list(map(json.loads, signatures_raw))
    if len(signatures) < 1:
        raise errors.NoRemoteSignatures("No signatures found for the image")
    return signatures
