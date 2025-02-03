import hashlib
import re
from collections import namedtuple
from typing import Dict, Optional, Tuple

import requests

from . import errors, log

__all__ = [
    "get_manifest_hash",
    "list_tags",
    "get_manifest",
    "get_attestation",
    "parse_image_location",
]

SIGSTORE_BUNDLE = "application/vnd.dev.sigstore.bundle.v0.3+json"
DOCKER_MANIFEST_DISTRIBUTION = "application/vnd.docker.distribution.manifest.v2+json"
DOCKER_MANIFEST_INDEX = "application/vnd.oci.image.index.v1+json"
OCI_IMAGE_MANIFEST = "application/vnd.oci.image.manifest.v1+json"


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
        self, tag: str, extra_headers: Optional[dict] = None
    ) -> requests.Response:
        """Get manifest information for a specific tag"""
        manifest_url = f"{self._image_url}/manifests/{tag}"
        headers = {
            "Accept": DOCKER_MANIFEST_DISTRIBUTION,
            "Authorization": f"Bearer {self.get_auth_token()}",
        }
        if extra_headers:
            headers.update(extra_headers)

        response = requests.get(manifest_url, headers=headers)
        response.raise_for_status()
        return response

    def list_manifests(self, tag: str) -> list:
        return (
            self.get_manifest(
                tag,
                {
                    "Accept": DOCKER_MANIFEST_INDEX,
                },
            )
            .json()
            .get("manifests")
        )

    def get_blob(self, hash: str) -> requests.Response:
        url = f"{self._image_url}/blobs/{hash}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.get_auth_token()}",
            },
        )
        response.raise_for_status()
        return response

    def get_manifest_hash(
        self, tag: str, tag_manifest_content: Optional[bytes] = None
    ) -> str:
        if not tag_manifest_content:
            tag_manifest_content = self.get_manifest(tag).content

        return hashlib.sha256(tag_manifest_content).hexdigest()

    def get_attestation(self, tag: str) -> Tuple[bytes, bytes]:
        """
        Retrieve an attestation from a given tag.

        The attestation needs to be attached using the Cosign Bundle
        Specification defined at:

        https://github.com/sigstore/cosign/blob/main/specs/BUNDLE_SPEC.md

        Returns a tuple with the tag manifest content and the bundle content.
        """

        # FIXME: do not only rely on the first layer
        def _find_sigstore_bundle_manifest(
            manifests: list,
        ) -> Tuple[Optional[str], Optional[str]]:
            for manifest in manifests:
                if manifest["artifactType"] == SIGSTORE_BUNDLE:
                    return manifest["mediaType"], manifest["digest"]
            return None, None

        def _get_bundle_blob_digest(layers: list) -> Optional[str]:
            for layer in layers:
                if layer.get("mediaType") == SIGSTORE_BUNDLE:
                    return layer["digest"]
            return None

        tag_manifest_content = self.get_manifest(tag).content

        # The attestation is available on the same container registry, with a
        # specific tag named "sha256-{sha256(manifest)}"
        tag_manifest_hash = self.get_manifest_hash(tag, tag_manifest_content)

        # This will get us a "list" of manifests...
        manifests = self.list_manifests(f"sha256-{tag_manifest_hash}")

        # ... from which we want the sigstore bundle
        bundle_manifest_mediatype, bundle_manifest_digest = (
            _find_sigstore_bundle_manifest(manifests)
        )
        if not bundle_manifest_digest:
            raise errors.RegistryError("Not able to find sigstore bundle manifest info")

        bundle_manifest = self.get_manifest(
            bundle_manifest_digest, extra_headers={"Accept": bundle_manifest_mediatype}
        ).json()

        # From there, we will get the attestation in a blob.
        # It will be the first layer listed at this manifest hash location
        layers = bundle_manifest.get("layers", [])

        blob_digest = _get_bundle_blob_digest(layers)
        log.info(f"Found sigstore bundle blob digest: {blob_digest}")
        if not blob_digest:
            raise errors.RegistryError("Not able to find sigstore bundle blob info")
        bundle = self.get_blob(blob_digest)
        return tag_manifest_content, bundle.content


def get_manifest_hash(image_str: str) -> str:
    image = parse_image_location(image_str)
    return RegistryClient(image).get_manifest_hash(image.tag)


def list_tags(image_str: str) -> list:
    return RegistryClient(image_str).list_tags()


def get_manifest(image_str: str) -> bytes:
    image = parse_image_location(image_str)
    client = RegistryClient(image)
    resp = client.get_manifest(image.tag, extra_headers={"Accept": OCI_IMAGE_MANIFEST})
    return resp.content


def get_attestation(image_str: str) -> Tuple[bytes, bytes]:
    image = parse_image_location(image_str)
    return RegistryClient(image).get_attestation(image.tag)
