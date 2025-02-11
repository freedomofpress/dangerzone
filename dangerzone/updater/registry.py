import re
from collections import namedtuple
from hashlib import sha256
from typing import Dict, Optional, Tuple

import requests

from . import errors, log

__all__ = [
    "get_manifest_digest",
    "list_tags",
    "get_manifest",
    "parse_image_location",
]

SIGSTORE_BUNDLE = "application/vnd.dev.sigstore.bundle.v0.3+json"
IMAGE_INDEX_MEDIA_TYPE = "application/vnd.oci.image.index.v1+json"
ACCEPT_MANIFESTS_HEADER = ",".join(
    [
        "application/vnd.docker.distribution.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v1+prettyjws",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        IMAGE_INDEX_MEDIA_TYPE,
    ]
)


Image = namedtuple("Image", ["registry", "namespace", "image_name", "tag"])


def parse_image_location(input_string: str) -> Image:
    """Parses container image location into an Image namedtuple"""
    pattern = (
        r"^"
        r"(?P<registry>[a-zA-Z0-9.-]+)/"
        r"(?P<namespace>[a-zA-Z0-9-]+)/"
        r"(?P<image_name>[^:]+)"
        r"(?::(?P<tag>[a-zA-Z0-9.-]+))?"
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
    )


def _get_auth_header(image) -> Dict[str, str]:
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


def _url(image):
    return f"https://{image.registry}/v2/{image.namespace}/{image.image_name}"


def list_tags(image_str: str) -> list:
    image = parse_image_location(image_str)
    url = f"{_url(image)}/tags/list"
    response = requests.get(url, headers=_get_auth_header(image))
    response.raise_for_status()
    tags = response.json().get("tags", [])
    return tags


def get_manifest(image_str) -> requests.Response:
    """Get manifest information for a specific tag"""
    image = parse_image_location(image_str)
    manifest_url = f"{_url(image)}/manifests/{image.tag}"
    headers = {
        "Accept": ACCEPT_MANIFESTS_HEADER,
    }
    headers.update(_get_auth_header(image))

    response = requests.get(manifest_url, headers=headers)
    response.raise_for_status()
    return response


def list_manifests(image_str) -> list:
    return get_manifest(image_str).json().get("manifests")


def get_blob(image, digest: str) -> requests.Response:
    response = requests.get(
        f"{_url(image)}/blobs/{digest}",
        headers={
            "Authorization": f"Bearer {_get_auth_token(image)}",
        },
    )
    response.raise_for_status()
    return response


def get_manifest_digest(
    image_str: str, tag_manifest_content: Optional[bytes] = None
) -> str:
    image = parse_image_location(image_str)
    if not tag_manifest_content:
        tag_manifest_content = get_manifest(image).content

    return sha256(tag_manifest_content).hexdigest()
