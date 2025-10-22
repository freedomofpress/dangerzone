import re
from collections import namedtuple
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Optional, Tuple

import requests

from .. import errors as dzerrors
from . import errors, log

# This client interacts with container registries as defined by:
# https://github.com/opencontainers/distribution-spec/blob/main/spec.md#endpoints

SIGSTORE_BUNDLE = "application/vnd.dev.sigstore.bundle.v0.3+json"
IMAGE_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
IMAGE_LIST_MEDIA_TYPE = "application/vnd.docker.distribution.manifest.list.v2+json"
ACCEPT_MANIFESTS_HEADER = ",".join(
    [
        "application/vnd.docker.distribution.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v1+prettyjws",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        IMAGE_LIST_MEDIA_TYPE,
        IMAGE_INDEX_MEDIA_TYPE,
    ]
)


@dataclass
class Image:
    registry: str
    namespace: str
    image_name: str
    tag: Optional[str] = None
    digest: Optional[str] = None

    def to_str(self) -> str:
        string = f"{self.registry}/{self.namespace}/{self.image_name}"
        # Do not output tag + digest if tag is latest
        # Only output the tag if:
        # - a tag is set and no digest is set
        # - OR a digest is set and the tag is latest
        if (self.tag and not self.digest) or (self.tag == "latest" and self.digest):
            string += f":{self.tag}"
        if self.digest:
            string += f"@sha256:{self.digest}"
        return string


def parse_image_location(input_string: str) -> Image:
    """Parses container image location into an Image namedtuple"""
    pattern = (
        r"^"
        r"(?P<registry>[a-zA-Z0-9.-]+)/"
        r"(?P<namespace>[a-zA-Z0-9-]+)/"
        r"(?P<image_name>[^:@]+)"
        r"(?::(?P<tag>[a-zA-Z0-9.-]+))?"
        r"(?:@(?P<digest>sha256:[a-zA-Z0-9]+))?"
        r"$"
    )
    match = re.match(pattern, input_string)
    if not match:
        raise ValueError("Malformed image location")
    return Image(
        registry=match.group("registry"),
        namespace=match.group("namespace"),
        image_name=match.group("image_name"),
        tag=match.group("tag") or "latest",
        digest=match.group("digest"),
    )


def replace_image_digest(image_str: str, digest: str, remove_tag: bool = True) -> str:
    image = parse_image_location(image_str)
    image.digest = digest
    if remove_tag:
        image.tag = None
    return image.to_str()


def _get_auth_header(image: Image) -> Dict[str, str]:
    log.info("Logging to the remote registry")
    auth_url = f"https://{image.registry}/token"
    response = requests.get(
        auth_url,
        params={
            "service": f"{image.registry}",
            "scope": f"repository:{image.namespace}/{image.image_name}:pull",
        },
    )
    response.raise_for_status()
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _url(image: Image) -> str:
    return f"https://{image.registry}/v2/{image.namespace}/{image.image_name}"


def get_manifest(image_str: str) -> requests.Response:
    """Get manifest information for a specific tag"""
    image = parse_image_location(image_str)
    if image.digest:
        manifest_url = f"{_url(image)}/manifests/{image.digest}"
    else:
        manifest_url = f"{_url(image)}/manifests/{image.tag}"
    headers = {
        "Accept": ACCEPT_MANIFESTS_HEADER,
    }
    headers.update(_get_auth_header(image))

    response = requests.get(manifest_url, headers=headers)
    response.raise_for_status()
    return response


def get_digest_for_arch(image_str: str, architecture: str) -> str:
    """Return the digest of the matching architecture, for the specified image, without the sha256: prefix"""
    manifest = get_manifest(image_str).json()

    if manifest.get("mediaType") != IMAGE_LIST_MEDIA_TYPE:
        raise errors.InvalidMutliArchImage()

    arch_manifests = [
        m["digest"].replace("sha256:", "")
        for m in manifest.get("manifests")
        if m["platform"]["architecture"] == architecture
    ]
    # There should be only one anyway, so let's return the first if there is one
    if not arch_manifests:
        raise errors.ArchitectureNotFound()
    return arch_manifests[0]


def list_manifests(image_str: str) -> list:
    return get_manifest(image_str).json().get("manifests")


def get_blob(image: Image, digest: str) -> requests.Response:
    response = requests.get(
        f"{_url(image)}/blobs/{digest}", headers=_get_auth_header(image)
    )
    response.raise_for_status()
    return response


def get_manifest_digest(
    image_str: str, tag_manifest_content: Optional[bytes] = None
) -> str:
    """Get the manifest for the specified image and return its digest."""
    if not tag_manifest_content:
        tag_manifest_content = get_manifest(image_str).content

    return sha256(tag_manifest_content).hexdigest()


def get_signature_manifest(image_str: str) -> Dict:
    """Returns the content of a signature for the given image"""
    digest = get_manifest_digest(image_str)
    image = parse_image_location(image_str)
    image.tag = "sha256-{digest}.sig"
    resp = get_manifest(image.to_str())
    return resp.json()
