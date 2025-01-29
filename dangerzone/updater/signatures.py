import json
import platform
import re
import subprocess
from base64 import b64decode
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Tuple

from .registry import RegistryClient
from .utils import write

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs


def get_config_dir() -> Path:
    return Path(platformdirs.user_config_dir("dangerzone"))


# XXX Store this somewhere else.
SIGNATURES_PATH = get_config_dir() / "signatures"
__all__ = [
    "verify_signature",
    "load_signatures",
    "store_signatures",
    "verify_local_image_signature",
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


def verify_signature(signature: dict, pubkey: str) -> bool:
    """Verify a signature against a given public key"""

    signature_bundle = signature_to_bundle(signature)

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="w") as signature_file,
        NamedTemporaryFile(mode="bw") as payload_file,
    ):
        json.dump(signature_bundle, signature_file)
        signature_file.flush()

        payload_bytes = b64decode(signature_bundle["Payload"])
        write(payload_file, payload_bytes)

        cmd = [
            "cosign",
            "verify-blob",
            "--key",
            pubkey,
            "--bundle",
            signature_file.name,
            payload_file.name,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # XXX Raise instead?
            return False
        return result.stderr == b"Verified OK\n"


def get_runtime_name() -> str:
    if platform.system() == "Linux":
        return "podman"
    return "docker"


def container_pull(image: str):
    # XXX - Move to container_utils.py
    cmd = [get_runtime_name(), "pull", f"{image}"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    process.communicate()
    return process.returncode == 0


def new_image_release():
    # XXX - Implement
    return True


def upgrade_container_image(
    image: str,
    manifest_hash: str,
    pubkey: str,
):
    if not new_image_release():
        return

    # manifest_hash = registry.get_manifest_hash(tag)
    signatures = get_signatures(image, manifest_hash)

    if len(signatures) < 1:
        raise Exception("Unable to retrieve signatures")

    for signature in signatures:
        signature_is_valid = verify_signature(signature, pubkey)
        if not signature_is_valid:
            raise Exception("Unable to verify signature")

    # At this point, the signatures are verified
    # We store the signatures just now to avoid storing unverified signatures
    store_signatures(signatures, manifest_hash, pubkey)

    # let's upgrade the image
    # XXX Use the hash here to avoid race conditions
    return container_pull(image)


def get_file_hash(file: str) -> str:
    with open(file, "rb") as f:
        content = f.read()
        return sha256(content).hexdigest()


def load_signatures(image_hash, pubkey):
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
        raise Exception(msg)

    with open(pubkey_signatures / f"{image_hash}.json") as f:
        return json.load(f)


def store_signatures(signatures: list[Dict], image_hash: str, pubkey: str):
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

    def _get_digest(sig):
        payload = json.loads(b64decode(sig["Payload"]))
        return payload["critical"]["image"]["docker-manifest-digest"]

    # All the signatures should share the same hash.
    hashes = list(map(_get_digest, signatures))
    if len(set(hashes)) != 1:
        raise Exception("Signatures do not share the same image hash")

    if f"sha256:{image_hash}" != hashes[0]:
        raise Exception("Signatures do not match the given image hash")

    pubkey_signatures = SIGNATURES_PATH / get_file_hash(pubkey)
    pubkey_signatures.mkdir(exist_ok=True)

    with open(pubkey_signatures / f"{image_hash}.json", "w") as f:
        json.dump(signatures, f)


def verify_offline_image_signature(image: str, pubkey: str) -> bool:
    """
    Verifies that a local image has a valid signature
    """
    image_hash = load_image_hash(image)
    signatures = load_signatures(image_hash, pubkey)
    if len(signatures) < 1:
        raise Exception("No signatures found")

    for signature in signatures:
        if not verify_signature(signature, pubkey):
            msg = f"Unable to verify signature for {image} with pubkey {pubkey}"
            raise Exception(msg)
    return True


def load_image_hash(image: str) -> str:
    """
    Returns a image hash from a local image name
    """
    cmd = [get_runtime_name(), "image", "inspect", image, "-f", "{{.Digest}}"]
    result = subprocess.run(cmd, capture_output=True, check=True)
    return result.stdout.strip().decode().strip("sha256:")


def get_signatures(image, hash) -> List[Dict]:
    """
    Retrieve the signatures from cosign download signature and convert each one to the "cosign bundle" format.
    """

    process = subprocess.run(
        ["cosign", "download", "signature", f"{image}@sha256:{hash}"],
        capture_output=True,
        check=True,
    )

    # XXX: Check the output first.
    # Remove the last return, split on newlines, convert from JSON
    signatures_raw = process.stdout.decode("utf-8").strip().split("\n")
    return list(map(json.loads, signatures_raw))
