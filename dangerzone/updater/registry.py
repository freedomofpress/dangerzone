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


class Image(namedtuple("Image", ["registry", "namespace", "image_name", "tag"])):
    __slots__ = ()

    @property
    def full_name(self) -> str:
        tag = f":{self.tag}" if self.tag else ""
        return f"{self.registry}/{self.namespace}/{self.image_name}{tag}"


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


class RegistryClient:
    def __init__(
        self,
        image: Image | str,
    ):
        if isinstance(image, str):
            image = parse_image_location(image)

        self._image = image
        self._registry = image.registry
        self._namespace = image.namespace
        self._image_name = image.image_name
        self._auth_token = None
        self._base_url = f"https://{self._registry}"
        self._image_url = f"{self._base_url}/v2/{self._namespace}/{self._image_name}"

    def get_auth_token(self) -> Optional[str]:
        if not self._auth_token:
            auth_url = f"{self._base_url}/token"
            response = requests.get(
                auth_url,
                params={
                    "service": f"{self._registry}",
                    "scope": f"repository:{self._namespace}/{self._image_name}:pull",
                },
            )
            response.raise_for_status()
            self._auth_token = response.json()["token"]
        return self._auth_token

    def get_auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.get_auth_token()}"}

    def list_tags(self) -> list:
        url = f"{self._image_url}/tags/list"
        response = requests.get(url, headers=self.get_auth_header())
        response.raise_for_status()
        tags = response.json().get("tags", [])
        return tags

    def get_manifest(
        self,
        tag: str,
    ) -> requests.Response:
        """Get manifest information for a specific tag"""
        manifest_url = f"{self._image_url}/manifests/{tag}"
        headers = {
            "Accept": ACCEPT_MANIFESTS_HEADER,
            "Authorization": f"Bearer {self.get_auth_token()}",
        }

        response = requests.get(manifest_url, headers=headers)
        response.raise_for_status()
        return response

    def list_manifests(self, tag: str) -> list:
        return (
            self.get_manifest(
                tag,
            )
            .json()
            .get("manifests")
        )

    def get_blob(self, digest: str) -> requests.Response:
        url = f"{self._image_url}/blobs/{digest}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.get_auth_token()}",
            },
        )
        response.raise_for_status()
        return response

    def get_manifest_digest(
        self, tag: str, tag_manifest_content: Optional[bytes] = None
    ) -> str:
        if not tag_manifest_content:
            tag_manifest_content = self.get_manifest(tag).content

        return sha256(tag_manifest_content).hexdigest()


# XXX Refactor this with regular functions rather than a class
def get_manifest_digest(image_str: str) -> str:
    image = parse_image_location(image_str)
    return RegistryClient(image).get_manifest_digest(image.tag)


def list_tags(image_str: str) -> list:
    return RegistryClient(image_str).list_tags()


def get_manifest(image_str: str) -> bytes:
    image = parse_image_location(image_str)
    client = RegistryClient(image)
    resp = client.get_manifest(image.tag)
    return resp.content
