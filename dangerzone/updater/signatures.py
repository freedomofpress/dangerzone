import json
import os
import platform
import re
import subprocess
import tarfile
from base64 import b64decode, b64encode
from dataclasses import dataclass
from functools import reduce
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Callable, Dict, List, Optional, Tuple

from .. import container_utils as runtime
from .. import errors as dzerrors
from ..container_utils import subprocess_run
from ..util import get_resource_path
from . import cosign, errors, log, registry

try:
    import platformdirs
except ImportError:
    import appdirs as platformdirs  # type: ignore[no-redef]


def appdata_dir() -> Path:
    return Path(platformdirs.user_data_dir("dangerzone"))


# RELEASE: Bump this value to the log index of the latest signature
# to ensure the software can't upgrade to container images that predates it.
BUNDLED_LOG_INDEX = 207673688

DEFAULT_PUBKEY_LOCATION = get_resource_path("freedomofpress-dangerzone.pub")
SIGNATURES_PATH = appdata_dir() / "signatures"
LAST_LOG_INDEX = SIGNATURES_PATH / "last_log_index"
DANGERZONE_MANIFEST = "dangerzone.json"


@dataclass
class Signature:
    """Utility class to interact with signatures"""

    signature: Dict

    @property
    def payload(self) -> Dict:
        return json.loads(self.payload_bytes)

    @property
    def payload_bytes(self) -> bytes:
        return b64decode(self.signature["Payload"])

    @property
    def manifest_digest(self) -> str:
        full_digest = self.payload["critical"]["image"]["docker-manifest-digest"]
        return full_digest.replace("sha256:", "")

    @property
    def log_index(self) -> int:
        return self.signature["Bundle"]["Payload"]["logIndex"]

    @property
    def bundle(self) -> Dict:
        return self.signature["Bundle"]

    @property
    def bundle_payload(self) -> Dict:
        return self.bundle["Payload"]

    def to_bundle(self) -> Dict:
        """Convert a cosign-download signature to the format expected by cosign bundle."""

        bundle = self.bundle
        payload = self.bundle_payload
        sig = self.signature

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


def verify_signature(signature: dict, image_digest: str, pubkey: Path) -> None:
    """
    Ensure that the given signature matches the public key and image digest
    passed as argument.

    Raises in case of errors.
    """
    # FIXME Also verify the identity/docker-reference field against
    # `container_utils.expected_image_name()`
    # e.g. ghcr.io/freedomofpress/dangerzone/dangerzone

    sig_obj = Signature(signature)
    try:
        payload_digest = sig_obj.payload["critical"]["image"]["docker-manifest-digest"]
    except Exception as e:
        raise errors.SignatureVerificationError(
            f"Unable to extract the payload digest from the signature: {e}"
        )
    if payload_digest != f"sha256:{image_digest}":
        raise errors.SignatureMismatch(
            "The given signature does not match the expected image digest "
            f"({payload_digest}, {image_digest})"
        )

    # Note: Pass delete=False here to avoid deleting the file before usage.
    # The file is read outside of the context manager otherwise it fails
    # on Windows, where the files can't be opened concurrently.
    #
    # Using a O_TEMPORARY flag mentioned in [0] is not practical here as how
    # cosign opens the file is not configurable.
    #
    # Hence the os.remove calls after calling cosign.verify_blob.
    #
    # [0] https://docs.python.org/3/library/tempfile.html#tempfile.NamedTemporaryFile
    with (
        NamedTemporaryFile(mode="w", delete=False) as signature_file,
        NamedTemporaryFile(mode="bw", delete=False) as payload_file,
    ):
        json.dump(sig_obj.to_bundle(), signature_file)
        signature_file.flush()

        payload_file.write(sig_obj.payload_bytes)
        payload_file.flush()

    try:
        cosign.verify_blob(pubkey, signature_file.name, payload_file.name)
        log.debug("Signature verified")
    finally:
        os.remove(signature_file.name)
        os.remove(payload_file.name)


def check_signatures_and_logindex(
    image_str: str,
    remote_digest: str,
    pubkey: Path,
    signatures: List[Dict],
    bypass_logindex_check: bool = False,
) -> list[Dict]:
    verify_signatures(signatures, remote_digest, pubkey)

    incoming_log_index = get_log_index_from_signatures(signatures)
    last_log_index = get_last_log_index()

    if not bypass_logindex_check:
        if incoming_log_index < last_log_index:
            raise errors.InvalidLogIndex(
                f"The incoming log index ({incoming_log_index}) is "
                f"lower than the last known log index ({last_log_index})"
            )
    return signatures


def verify_signatures(
    signatures: List[Dict],
    image_digest: str,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
) -> None:
    if len(signatures) < 1:
        raise errors.SignatureVerificationError("No signatures found")

    for signature in signatures:
        # Will raise on errors
        verify_signature(signature, image_digest, pubkey)


def get_last_log_index() -> int:
    SIGNATURES_PATH.mkdir(parents=True, exist_ok=True)
    if not LAST_LOG_INDEX.exists():
        return BUNDLED_LOG_INDEX

    with open(LAST_LOG_INDEX) as f:
        return int(f.read())


def get_log_index_from_signatures(signatures: List[Dict]) -> int:
    def _reducer(accumulator: int, signature: Dict) -> int:
        try:
            logIndex = int(signature["Bundle"]["Payload"]["logIndex"])
        except (KeyError, ValueError):
            log.debug("Discarding invalid logindex")
            return accumulator
        return max(accumulator, logIndex)

    return reduce(_reducer, signatures, 0)


def write_log_index(log_index: int) -> None:
    last_log_index_path = SIGNATURES_PATH / "last_log_index"

    with open(last_log_index_path, "w") as f:
        f.write(str(log_index))


def _get_images_only_manifest(input: dict) -> dict:
    """Filter out all the non-images from a loaded manifest"""
    output = input.copy()
    output["manifests"] = [
        manifest
        for manifest in input["manifests"]
        if manifest["annotations"].get("kind")
        in ("dev.cosignproject.cosign/imageIndex", "dev.cosignproject.cosign/image")
    ]
    return output


def _get_blob(digest: str) -> PurePath:
    return PurePath() / "blobs" / "sha256" / digest.replace("sha256:", "")


def _get_signature_filename(input: Dict) -> PurePath:
    for manifest in input["manifests"]:
        if manifest["annotations"].get("kind") == "dev.cosignproject.cosign/sigs":
            return _get_blob(manifest["digest"])
    raise errors.SignatureExtractionError()


def upgrade_container_image_airgapped(
    container_tar: Path,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
    bypass_logindex: bool = False,
) -> str:
    """
    Verify the given archive against its self-contained signatures, then
    upgrade the image and retag it to the expected tag.

    The logic supports both "dangerzone archives" only, which have
    `dangerzone.json` file at the root of the tarball.

    See `prepare_airgapped_archive` for more details.

    :return: The loaded image name
    """

    with TemporaryDirectory() as _tempdir, tarfile.open(container_tar, "r") as archive:
        # First, check the archive type
        files = archive.getnames()
        tmppath = Path(_tempdir)

        has_dangerzone_manifest = f"./{DANGERZONE_MANIFEST}" in files
        if not has_dangerzone_manifest:
            raise errors.InvalidImageArchive()

        # Ensure that the signatures.json is the same as the index.json
        # with only the images remaining, to avoid situations where we
        # check the signatures but the index.json differs, making us
        # think that we're with valid signatures where we indeed aren't.
        archive.extract(f"./{DANGERZONE_MANIFEST}", tmppath)
        archive.extract("./index.json", tmppath)

        with (
            (tmppath / DANGERZONE_MANIFEST).open() as dzf,
            (tmppath / "index.json").open() as indexf,
        ):
            dz_manifest = json.load(dzf)
            index_manifest = json.load(indexf)

        expected_manifest = _get_images_only_manifest(dz_manifest)
        if expected_manifest != index_manifest:
            raise errors.InvalidDangerzoneManifest()

        signature_filename = _get_signature_filename(dz_manifest)
        archive.extract(f"./{signature_filename.as_posix()}", tmppath)

        with (tmppath / signature_filename).open() as f:
            image_name, signatures = convert_oci_images_signatures(
                json.load(f), archive, tmppath
            )
        log.info(f"Found image name: {image_name}")

    if not bypass_logindex:
        # Ensure that we only upgrade if the log index is higher than the last known one
        incoming_log_index = get_log_index_from_signatures(signatures)
        last_log_index = get_last_log_index()

        if incoming_log_index < last_log_index:
            raise errors.InvalidLogIndex(
                "The log index is not higher than the last known one"
            )

    image_digest = dz_manifest["manifests"][0].get("digest").replace("sha256:", "")

    runtime.load_image_tarball(container_tar)
    # Apply the tag manually here, since images downloaded with `cosign download`
    # do not come with the tags attached.
    runtime.tag_image_by_digest(image_digest, image_name)

    try:
        verify_signatures(signatures, image_digest)
        store_signatures(signatures, image_digest, pubkey)
    except errors.SignatureError as e:
        log.info("Unable to verify the signatures, unload the image")
        runtime.delete_image_digests([f"sha256:{image_digest}"], image_name)
        raise e

    return image_name


def get_blob_from_archive(digest: str, tmppath: Path, archive: tarfile.TarFile) -> Path:
    """
    Extracts the blob from the given archive, place it in the given path and
    return its Path.
    """
    relpath = _get_blob(digest)
    archive.extract(f"./{relpath.as_posix()}", tmppath)
    return tmppath / relpath


def convert_oci_images_signatures(
    signatures_manifest: Dict, archive: tarfile.TarFile, tmppath: Path
) -> Tuple[str, List[Dict]]:
    """
    Convert OCI images signatures (from the registry) to
    cosign-compatible signatures.
    """

    def _to_cosign_signature(layer: Dict) -> Dict:
        signature = layer["annotations"]["dev.cosignproject.cosign/signature"]
        bundle = json.loads(layer["annotations"]["dev.sigstore.cosign/bundle"])
        payload_body = json.loads(b64decode(bundle["Payload"]["body"]))

        payload_path = get_blob_from_archive(layer["digest"], tmppath, archive)

        with (payload_path).open("rb") as f:
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

    payload_location = get_blob_from_archive(layers[0]["digest"], tmppath, archive)
    with open(payload_location, "r") as f:
        payload = json.load(f)
        image_name = payload["critical"]["identity"]["docker-reference"]

    return image_name, signatures


def get_remote_log_index(image_str: str) -> int:
    """Check the registry to find the remote log index for the given image"""
    try:
        signature_manifest = registry.get_signature_manifest(image_str)
        return get_log_index_from_oci_signatures(signature_manifest)
    except:
        return 0


def get_log_index_from_oci_signatures(signature_manifest: dict) -> int:
    """
    Extracts the log index from OCI signatures without having
    to parse and verify the whole signature.
    """
    remote_log_index = 0
    for layer in signature_manifest["layers"]:
        bundle = json.loads(layer["annotations"]["dev.sigstore.cosign/bundle"])
        log_index = bundle["Payload"]["logIndex"]
        if log_index > remote_log_index:
            remote_log_index = log_index
    return remote_log_index


def get_file_digest(
    path: Optional[Path] = None, content: Optional[bytes] = None
) -> str:
    """Get the sha256 digest of a file or content"""
    if not path and not content:
        raise errors.UpdaterError("No file or content provided")
    if path:
        with path.open("rb") as f:
            content = f.read()
    if content:
        return sha256(content).hexdigest()
    return ""


def load_and_verify_signatures(
    image_digest: str,
    pubkey: Path,
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
            f"Cannot find a '{pubkey_signatures}' folder. "
            "You might need to download the image signatures first."
        )
        raise errors.SignaturesFolderDoesNotExist(msg)

    signatures_file = pubkey_signatures / f"{image_digest}.json"

    if not signatures_file.exists():
        msg = (
            f"Cannot find a '{signatures_file}' file. "
            "You might need to download the image signatures first."
        )
        raise errors.LocalSignatureNotFound(msg)

    with open(signatures_file) as f:
        log.debug("Loading signatures from %s", f.name)
        signatures = json.load(f)

    if not bypass_verification:
        verify_signatures(signatures, image_digest, pubkey)

    return signatures


def store_signatures(
    signatures: list[Dict],
    image_digest: str,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
    update_logindex: bool = True,
) -> None:
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
    signature`, which differs from the "bundle" one used in the code.

    It can be converted to the one expected by cosign verify --bundle with
    the `Signature.to_bundle()` method.

    This function must be used only if the provided signatures have been verified.
    """

    def _get_digest(sig: Dict) -> str:
        payload = json.loads(b64decode(sig["Payload"]))
        return payload["critical"]["image"]["docker-manifest-digest"]

    # All the signatures should share the same digest.
    digests = list(map(_get_digest, signatures))
    if len(set(digests)) != 1:
        raise errors.SignatureMismatch("Signatures do not share the same image digest")

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

    if update_logindex:
        write_log_index(get_log_index_from_signatures(signatures))


def verify_local_image(
    image: Optional[str] = None,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
    image_digest: Optional[str] = None,
) -> bool:
    """
    Verifies that a local image has a valid signature
    """
    if not image_digest:
        if image is None:
            image = runtime.expected_image_name()
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
    signatures_raw = cosign.download_signature(image, digest)
    signatures = list(filter(bool, map(json.loads, signatures_raw)))
    if len(signatures) < 1:
        raise errors.NoRemoteSignatures("No signatures found for the image")
    return signatures


def prepare_airgapped_archive(
    image_name: str,
    destination: str,
    architecture: str,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
) -> None:
    """
    Prepare a container image tarball to be used in environments without doing
    a {podman,docker} pull.

    Podman and Docker are not able to load archives for which the index.json file
    contains signatures and attestations, so they are removed from the resulting
    index.json.

    The original index.json is copied to dangerzone.json to be able to refer to
    it when verifying the signatures.
    """

    # Find out if this is a multi-archi image or not
    arch_digest = registry.get_digest_for_arch(image_name, architecture)
    arch_image = registry.replace_image_digest(image_name, arch_digest)

    log.info(f"Found an image for architecture '{architecture}' at '{arch_image}'")

    # Get the image from the registry
    with TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        msg = f"Downloading image {arch_image}. \nIt might take a while."
        log.info(msg)
        log.debug(f"Downloading to temporary directory {str(tmpdir)}")

        cosign.save(arch_image, tmppath)
        cosign.verify_local_image(tmppath, pubkey)

        # Read from index.json, save it as DANGERZONE_MANIFEST
        # and then change the index.json contents to only contain
        # images (noting this as the naming might sound awkward)
        with (
            (tmppath / "index.json").open() as indexf,
            (tmppath / DANGERZONE_MANIFEST).open("w+") as dzf,
        ):
            original_index_json = json.load(indexf)
            json.dump(original_index_json, dzf)

        new_index_json = _get_images_only_manifest(original_index_json)

        # Write the new index.json to the temp folder
        with open(tmppath / "index.json", "w") as f:
            json.dump(new_index_json, f)

        with tarfile.open(destination, "w") as archive:
            # The root is the tmpdir
            # archive.add(tmppath / "index.json", arcname="index.json")
            # archive.add(tmppath / "oci-layout", arcname="oci-layout")
            # archive.add(tmppath / "blobs", arcname="blobs")
            archive.add(str(tmppath), arcname=".")


def get_remote_digest_and_logindex(
    image_str: str, pubkey: Path = DEFAULT_PUBKEY_LOCATION
) -> Tuple[str, int, List[Dict]]:
    """
    Check the remote container registry for updates, downloads and verify
    the signatures and extract log index from them.

    Returns a tuple of (remote_digest, remote_log_index)
    """
    log.info("Get manifest digests")
    remote_digest = registry.get_manifest_digest(image_str)

    log.info("Get remote signatures")
    signatures = get_remote_signatures(image_str, remote_digest)

    log.info("Verify signatures")
    verify_signatures(signatures, remote_digest, pubkey)

    log.info("Getting log index from signatures")
    remote_log_index = get_log_index_from_signatures(signatures)
    return (remote_digest, remote_log_index, signatures)


def upgrade_container_image(
    remote_digest: str,
    image_str: Optional[str] = None,
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
    bypass_logindex_check: bool = False,
    callback: Optional[Callable] = None,
    signatures: Optional[List[Dict]] = None,
) -> None:
    """Verify and upgrade the image to the latest, if signed."""
    image_str = image_str or runtime.expected_image_name()

    # Avoid downloading again the signatures if we just did it previously
    if not signatures:
        signatures = get_remote_signatures(image_str, remote_digest)

    check_signatures_and_logindex(
        image_str,
        remote_digest,
        pubkey,
        signatures,
        bypass_logindex_check,
    )
    runtime.container_pull(image_str, remote_digest, callback=callback)

    # Now that they are verified, store the signatures
    store_signatures(signatures, remote_digest, pubkey)


def install_local_container_tar(
    pubkey: Path = DEFAULT_PUBKEY_LOCATION,
) -> None:
    tarball_path = get_resource_path("container.tar")
    log.debug("Installing container image %s", tarball_path)
    upgrade_container_image_airgapped(tarball_path, pubkey)
