import json
import platform
import re
import subprocess
import tarfile
from base64 import b64decode, b64encode
from functools import reduce
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Dict, List, Optional, Tuple

from .. import container_utils as runtime
from .. import errors as dzerrors
from ..util import get_resource_path
from . import cosign, errors, log, registry

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs  # type: ignore[no-redef]


def appdata_dir() -> Path:
    return Path(platformdirs.user_data_dir("dangerzone"))


# RELEASE: Bump this value to the log index of the latest signature
# to ensures the software can't upgrade to container images that predates it.
DEFAULT_LOG_INDEX = 0

# XXX Store this somewhere else.
DEFAULT_PUBKEY_LOCATION = get_resource_path("freedomofpress-dangerzone-pub.key")
SIGNATURES_PATH = appdata_dir() / "signatures"
LAST_LOG_INDEX = SIGNATURES_PATH / "last_log_index"

__all__ = [
    "verify_signature",
    "load_and_verify_signatures",
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


def verify_signature(signature: dict, image_digest: str, pubkey: str | Path) -> None:
    """
    Verifies that:

    - the signature has been signed by the given public key
    - the signature matches the given image digest
    """
    # XXX - Also verify the identity/docker-reference field against the expected value
    # e.g. ghcr.io/freedomofpress/dangerzone/dangerzone

    cosign.ensure_installed()
    signature_bundle = signature_to_bundle(signature)
    try:
        payload_bytes = b64decode(signature_bundle["Payload"])
        payload_digest = json.loads(payload_bytes)["critical"]["image"][
            "docker-manifest-digest"
        ]
    except Exception as e:
        raise errors.SignatureVerificationError(
            f"Unable to extract the payload digest from the signature: {e}"
        )
    if payload_digest != f"sha256:{image_digest}":
        raise errors.SignatureMismatch(
            "The given signature does not match the expected image digest "
            f"({payload_digest}, {image_digest})"
        )

    with (
        NamedTemporaryFile(mode="w") as signature_file,
        NamedTemporaryFile(mode="bw") as payload_file,
    ):
        json.dump(signature_bundle, signature_file)
        signature_file.flush()

        payload_file.write(payload_bytes)
        payload_file.flush()

        if isinstance(pubkey, str):
            pubkey = Path(pubkey)

        cmd = [
            "cosign",
            "verify-blob",
            "--key",
            str(pubkey.absolute()),
            "--bundle",
            signature_file.name,
            payload_file.name,
        ]
        log.debug(" ".join(cmd))
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0 or result.stderr != b"Verified OK\n":
            log.debug("Failed to verify signature", result.stderr)
            raise errors.SignatureVerificationError("Failed to verify signature")
        log.debug("Signature verified")


class Signature:
    def __init__(self, signature: Dict):
        self.signature = signature

    @property
    def payload(self) -> Dict:
        return json.loads(b64decode(self.signature["Payload"]))

    @property
    def manifest_digest(self) -> str:
        full_digest = self.payload["critical"]["image"]["docker-manifest-digest"]
        return full_digest.replace("sha256:", "")


def is_update_available(image: str) -> Tuple[bool, Optional[str]]:
    remote_digest = registry.get_manifest_digest(image)
    try:
        local_digest = runtime.get_local_image_digest(image)
    except dzerrors.ImageNotPresentException:
        log.debug("No local image found")
        return True, remote_digest
    log.debug("Remote digest: %s", remote_digest)
    log.debug("Local digest: %s", local_digest)
    has_update = remote_digest != local_digest
    if has_update:
        return True, remote_digest
    return False, None


def verify_signatures(
    signatures: List[Dict],
    image_digest: str,
    pubkey: str,
) -> bool:
    if len(signatures) < 1:
        raise errors.SignatureVerificationError("No signatures found")

    for signature in signatures:
        verify_signature(signature, image_digest, pubkey)
    return True


def get_last_log_index() -> int:
    SIGNATURES_PATH.mkdir(parents=True, exist_ok=True)
    if not LAST_LOG_INDEX.exists():
        return DEFAULT_LOG_INDEX

    with open(LAST_LOG_INDEX) as f:
        return int(f.read())


def get_log_index_from_signatures(signatures: List[Dict]) -> int:
    def _reducer(accumulator: int, signature: Dict) -> int:
        try:
            logIndex = int(signature["Bundle"]["Payload"]["logIndex"])
        except (KeyError, ValueError):
            return accumulator
        return max(accumulator, logIndex)

    return reduce(_reducer, signatures, 0)


def write_log_index(log_index: int) -> None:
    last_log_index_path = SIGNATURES_PATH / "last_log_index"

    with open(last_log_index_path, "w") as f:
        f.write(str(log_index))


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

        # Remove the signatures from the archive, otherwise podman is not able to load it
        with open(Path(tmpdir) / "index.json") as f:
            index_json = json.load(f)

        signature_filename = _get_signature_filename(index_json["manifests"])

        index_json["manifests"] = [
            manifest
            for manifest in index_json["manifests"]
            if manifest["annotations"].get("kind")
            in ("dev.cosignproject.cosign/imageIndex", "dev.cosignproject.cosign/image")
        ]

        with open(signature_filename, "r") as f:
            image_name, signatures = convert_oci_images_signatures(json.load(f), tmpdir)
        log.info(f"Found image name: {image_name}")

        # Ensure that we only upgrade if the log index is higher than the last known one
        incoming_log_index = get_log_index_from_signatures(signatures)
        last_log_index = get_last_log_index()

        if incoming_log_index < last_log_index:
            raise errors.InvalidLogIndex(
                "The log index is not higher than the last known one"
            )

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

            runtime.load_image_tarball_from_tar(temporary_tar.name)
            runtime.tag_image_by_digest(image_digest, image_name)

    store_signatures(signatures, image_digest, pubkey)
    return image_name


def convert_oci_images_signatures(
    signatures_manifest: Dict, tmpdir: str
) -> Tuple[str, List[Dict]]:
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

    layers = signatures_manifest.get("layers", [])
    signatures = [_to_cosign_signature(layer) for layer in layers]

    if not signatures:
        raise errors.SignatureExtractionError()

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


def load_and_verify_signatures(
    image_digest: str,
    pubkey: str,
    bypass_verification: bool = False,
    signatures_path: Optional[Path] = None,
) -> List[Dict]:
    """
    Load signatures from the local filesystem

    See store_signatures() for the expected format.
    """
    if not signatures_path:
        signatures_path = SIGNATURES_PATH

    pubkey_signatures = signatures_path / get_file_digest(pubkey)
    if not pubkey_signatures.exists():
        msg = (
            f"Cannot find a '{pubkey_signatures}' folder."
            "You might need to download the image signatures first."
        )
        raise errors.SignaturesFolderDoesNotExist(msg)

    with open(pubkey_signatures / f"{image_digest}.json") as f:
        log.debug("Loading signatures from %s", f.name)
        signatures = json.load(f)

    if not bypass_verification:
        verify_signatures(signatures, image_digest, pubkey)

    return signatures


def store_signatures(signatures: list[Dict], image_digest: str, pubkey: str) -> None:
    """
    Store signatures locally in the SIGNATURE_PATH folder, like this:

    ~/.config/dangerzone/signatures/
    ├── <pubkey-digest>
    │   ├── <image-digest>.json
    │   ├── <image-digest>.json
    └── last_log_index

    The last_log_index file is used to keep track of the last log index
    processed by the updater.

    The format used in the `.json` file is the one of `cosign download
    signature`, which differs from the "bundle" one used afterwards.

    It can be converted to the one expected by cosign verify --bundle with
    the `signature_to_bundle()` function.

    This function must be used only if the provided signatures have been verified.
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
            f"Signatures do not match the given image digest (sha256:{image_digest}, {digests[0]})"
        )

    pubkey_signatures = SIGNATURES_PATH / get_file_digest(pubkey)
    pubkey_signatures.mkdir(parents=True, exist_ok=True)

    with open(pubkey_signatures / f"{image_digest}.json", "w") as f:
        log.info(
            f"Storing signatures for {image_digest} in {pubkey_signatures}/{image_digest}.json"
        )
        json.dump(signatures, f)

    write_log_index(get_log_index_from_signatures(signatures))


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
    load_and_verify_signatures(image_digest, pubkey)
    return True


def get_remote_signatures(image: str, digest: str) -> List[Dict]:
    """Retrieve the signatures from the registry, via `cosign download signatures`."""
    cosign.ensure_installed()

    try:
        process = subprocess.run(
            ["cosign", "download", "signature", f"{image}@sha256:{digest}"],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.NoRemoteSignatures(e)

    # Remove the last return, split on newlines, convert from JSON
    signatures_raw = process.stdout.decode("utf-8").strip().split("\n")
    signatures = list(filter(bool, map(json.loads, signatures_raw)))
    if len(signatures) < 1:
        raise errors.NoRemoteSignatures("No signatures found for the image")
    return signatures


def prepare_airgapped_archive(image_name: str, destination: str) -> None:
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


def upgrade_container_image(image: str, manifest_digest: str, pubkey: str) -> str:
    """Verify and upgrade the image to the latest, if signed."""
    update_available, _ = is_update_available(image)
    if not update_available:
        raise errors.ImageAlreadyUpToDate("The image is already up to date")

    signatures = get_remote_signatures(image, manifest_digest)
    verify_signatures(signatures, manifest_digest, pubkey)

    # Only upgrade if the log index is higher than the last known one
    incoming_log_index = get_log_index_from_signatures(signatures)
    last_log_index = get_last_log_index()

    if incoming_log_index < last_log_index:
        raise errors.InvalidLogIndex(
            "Trying to upgrade to an image with a lower log index"
        )

    runtime.container_pull(image, manifest_digest)

    # Store the signatures just now to avoid storing them unverified
    store_signatures(signatures, manifest_digest, pubkey)
    return manifest_digest
