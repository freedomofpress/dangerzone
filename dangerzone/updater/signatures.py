import json
import platform
import re
import subprocess
import tarfile
from base64 import b64decode, b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Dict, List, Optional, Tuple

from .. import container_utils as runtime
from . import cosign, errors, log, registry

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


def verify_signature(signature: dict, image_digest: str, pubkey: str) -> bool:
    """Verify a signature against a given public key"""
    # XXX - Also verfy the identity/docker-reference field against the expected value
    # e.g. ghcr.io/freedomofpress/dangerzone/dangerzone

    cosign.ensure_installed()
    signature_bundle = signature_to_bundle(signature)

    payload_bytes = b64decode(signature_bundle["Payload"])
    payload_digest = json.loads(payload_bytes)["critical"]["image"][
        "docker-manifest-digest"
    ]
    if payload_digest != f"sha256:{image_digest}":
        raise errors.SignatureMismatch(
            f"The signature does not match the image digest ({payload_digest}, {image_digest})"
        )

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


def is_update_available(image: str) -> bool:
    remote_digest = registry.get_manifest_digest(image)
    local_digest = runtime.get_local_image_digest(image)
    log.debug("Remote digest: %s", remote_digest)
    log.debug("Local digest: %s", local_digest)
    return remote_digest != local_digest


def verify_signatures(
    signatures: List[Dict],
    image_digest: str,
    pubkey: str,
) -> bool:
    for signature in signatures:
        if not verify_signature(signature, image_digest, pubkey):
            raise errors.SignatureVerificationError()
    return True


def upgrade_container_image(image: str, manifest_digest: str, pubkey: str) -> bool:
    """Verify and upgrade the image to the latest, if signed."""
    if not is_update_available(image):
        raise errors.ImageAlreadyUpToDate("The image is already up to date")

    signatures = get_remote_signatures(image, manifest_digest)
    verify_signatures(signatures, manifest_digest, pubkey)

    # At this point, the signatures are verified
    # We store the signatures just now to avoid storing unverified signatures
    store_signatures(signatures, manifest_digest, pubkey)

    # let's upgrade the image
    # XXX Use the image digest here to avoid race conditions
    return runtime.container_pull(image)


def _get_blob(tmpdir: str, digest: str) -> Path:
    return Path(tmpdir) / "blobs" / "sha256" / digest.replace("sha256:", "")


def upgrade_container_image_airgapped(container_tar: str, pubkey: str) -> str:
    """
    Verify the given archive against its self-contained signatures, then
    upgrade the image and retag it to the expected tag.

    Right now, the archive is extracted and reconstructed, requiring some space
    on the filesystem.

    :return: The loaded image name
    """

    # XXX Use a memory buffer instead of the filesystem
    with TemporaryDirectory() as tmpdir:

        def _get_signature_filename(manifests: List[Dict]) -> Path:
            for manifest in manifests:
                if (
                    manifest["annotations"].get("kind")
                    == "dev.cosignproject.cosign/sigs"
                ):
                    return _get_blob(tmpdir, manifest["digest"])
            raise errors.SignatureExtractionError()

        with tarfile.open(container_tar, "r") as archive:
            archive.extractall(tmpdir)

        if not cosign.verify_local_image(tmpdir, pubkey):
            raise errors.SignatureVerificationError()

        # Remove the signatures from the archive.
        with open(Path(tmpdir) / "index.json") as f:
            index_json = json.load(f)

        signature_filename = _get_signature_filename(index_json["manifests"])

        index_json["manifests"] = [
            manifest
            for manifest in index_json["manifests"]
            if manifest["annotations"].get("kind")
            in ("dev.cosignproject.cosign/imageIndex", "dev.cosignproject.cosign/image")
        ]

        with open(signature_filename, "rb") as f:
            image_name, signatures = convert_oci_images_signatures(json.load(f), tmpdir)
        log.info(f"Found image name: {image_name}")

        image_digest = index_json["manifests"][0].get("digest").replace("sha256:", "")

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

    store_signatures(signatures, image_digest, pubkey)
    return image_name


def convert_oci_images_signatures(
    signatures_manifest: List[Dict], tmpdir: str
) -> (str, List[Dict]):
    def _to_cosign_signature(layer: Dict) -> Dict:
        signature = layer["annotations"]["dev.cosignproject.cosign/signature"]
        bundle = json.loads(layer["annotations"]["dev.sigstore.cosign/bundle"])
        payload_body = json.loads(b64decode(bundle["Payload"]["body"]))

        payload_location = _get_blob(tmpdir, layer["digest"])
        with open(payload_location, "rb") as f:
            payload_b64 = b64encode(f.read()).decode()

        return {
            "Base64Signature": payload_body["spec"]["signature"]["content"],
            "Payload": payload_b64,
            "Cert": None,
            "Chain": None,
            "Bundle": bundle,
            "RFC3161Timestamp": None,
        }

    layers = signatures_manifest["layers"]
    signatures = [_to_cosign_signature(layer) for layer in layers]

    payload_location = _get_blob(tmpdir, layers[0]["digest"])
    with open(payload_location, "r") as f:
        payload = json.load(f)
        image_name = payload["critical"]["identity"]["docker-reference"]

    return image_name, signatures


def get_file_digest(file: Optional[str] = None, content: Optional[bytes] = None) -> str:
    """Get the sha256 digest of a file or content"""
    if not file and not content:
        raise errors.UpdaterError("No file or content provided")
    if file:
        with open(file, "rb") as f:
            content = f.read()
    if content:
        return sha256(content).hexdigest()
    return ""


def load_signatures(image_digest: str, pubkey: str) -> List[Dict]:
    """
    Load signatures from the local filesystem

    See store_signatures() for the expected format.
    """
    pubkey_signatures = SIGNATURES_PATH / get_file_digest(pubkey)
    if not pubkey_signatures.exists():
        msg = (
            f"Cannot find a '{pubkey_signatures}' folder."
            "You might need to download the image signatures first."
        )
        raise errors.SignaturesFolderDoesNotExist(msg)

    with open(pubkey_signatures / f"{image_digest}.json") as f:
        log.debug("Loading signatures from %s", f.name)
        return json.load(f)


def store_signatures(signatures: list[Dict], image_digest: str, pubkey: str) -> None:
    """
    Store signatures locally in the SIGNATURE_PATH folder, like this:

    ~/.config/dangerzone/signatures/
    └── <pubkey-digest>
        └── <image-digest>.json
        └── <image-digest>.json

    The format used in the `.json` file is the one of `cosign download
    signature`, which differs from the "bundle" one used afterwards.

    It can be converted to the one expected by cosign verify --bundle with
    the `signature_to_bundle()` function.
    """

    def _get_digest(sig: Dict) -> str:
        payload = json.loads(b64decode(sig["Payload"]))
        return payload["critical"]["image"]["docker-manifest-digest"]

    # All the signatures should share the same digest.
    digests = list(map(_get_digest, signatures))
    if len(set(digests)) != 1:
        raise errors.InvalidSignatures("Signatures do not share the same image digest")

    if f"sha256:{image_digest}" != digests[0]:
        raise errors.SignatureMismatch(
            f"Signatures do not match the given image digest ({image_digest}, {digests[0]})"
        )

    pubkey_signatures = SIGNATURES_PATH / get_file_digest(pubkey)
    pubkey_signatures.mkdir(parents=True, exist_ok=True)

    with open(pubkey_signatures / f"{image_digest}.json", "w") as f:
        log.info(
            f"Storing signatures for {image_digest} in {pubkey_signatures}/{image_digest}.json"
        )
        json.dump(signatures, f)


def verify_local_image(image: str, pubkey: str) -> bool:
    """
    Verifies that a local image has a valid signature
    """
    log.info(f"Verifying local image {image} against pubkey {pubkey}")
    try:
        image_digest = runtime.get_local_image_digest(image)
    except subprocess.CalledProcessError:
        raise errors.ImageNotFound(f"The image {image} does not exist locally")

    log.debug(f"Image digest: {image_digest}")
    signatures = load_signatures(image_digest, pubkey)
    if len(signatures) < 1:
        raise errors.LocalSignatureNotFound("No signatures found")

    for signature in signatures:
        if not verify_signature(signature, image_digest, pubkey):
            msg = f"Unable to verify signature for {image} with pubkey {pubkey}"
            raise errors.SignatureVerificationError(msg)
    return True


def get_remote_signatures(image: str, digest: str) -> List[Dict]:
    """Retrieve the signatures from the registry, via `cosign download`."""
    cosign.ensure_installed()

    process = subprocess.run(
        ["cosign", "download", "signature", f"{image}@sha256:{digest}"],
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


def prepare_airgapped_archive(image_name, destination):
    if "@sha256:" not in image_name:
        raise errors.AirgappedImageDownloadError(
            "The image name must include a digest, e.g. ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:123456"
        )

    cosign.ensure_installed()
    # Get the image from the registry

    with TemporaryDirectory() as tmpdir:
        msg = f"Downloading image {image_name}. \nIt might take a while."
        log.info(msg)

        process = subprocess.run(
            ["cosign", "save", image_name, "--dir", tmpdir],
            capture_output=True,
            check=True,
        )
        if process.returncode != 0:
            raise errors.AirgappedImageDownloadError()

        with tarfile.open(destination, "w") as archive:
            archive.add(tmpdir, arcname=".")
