#!/usr/bin/python

import hashlib
import json
import platform
import re
import shutil
import subprocess
from base64 import b64decode
from tempfile import NamedTemporaryFile

import click
import requests

DEFAULT_REPO = "freedomofpress/dangerzone"
SIGSTORE_BUNDLE = "application/vnd.dev.sigstore.bundle.v0.3+json"
DOCKER_MANIFEST_DISTRIBUTION = "application/vnd.docker.distribution.manifest.v2+json"
DOCKER_MANIFEST_INDEX = "application/vnd.oci.image.index.v1+json"
OCI_IMAGE_MANIFEST = "application/vnd.oci.image.manifest.v1+json"


class RegistryClient:
    def __init__(self, registry, org, image):
        self._registry = registry
        self._org = org
        self._image = image
        self._auth_token = None
        self._base_url = f"https://{registry}"
        self._image_url = f"{self._base_url}/v2/{self._org}/{self._image}"

    @property
    def image(self):
        return f"{self._registry}/{self._org}/{self._image}"

    def get_auth_token(self):
        if not self._auth_token:
            auth_url = f"{self._base_url}/token"
            response = requests.get(
                auth_url,
                params={
                    "service": f"{self._registry}",
                    "scope": f"repository:{self._org}/{self._image}:pull",
                },
            )
            response.raise_for_status()
            self._auth_token = response.json()["token"]
        return self._auth_token

    def get_auth_header(self):
        return {"Authorization": f"Bearer {self.get_auth_token()}"}

    def list_tags(self):
        url = f"{self._image_url}/tags/list"
        response = requests.get(url, headers=self.get_auth_header())
        response.raise_for_status()
        tags = response.json().get("tags", [])
        return tags

    def get_manifest(self, tag, extra_headers=None):
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

    def list_manifests(self, tag):
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

    def get_blob(self, hash):
        url = f"{self._image_url}/blobs/{hash}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.get_auth_token()}",
            },
        )
        response.raise_for_status()
        return response

    def get_manifest_hash(self, tag, tag_manifest_content=None):
        if not tag_manifest_content:
            tag_manifest_content = self.get_manifest(tag).content

        return hashlib.sha256(tag_manifest_content).hexdigest()

    def get_attestation(self, tag):
        """
        Retrieve an attestation from a given tag.

        The attestation needs to be attached using the Cosign Bundle
        Specification defined at:

        https://github.com/sigstore/cosign/blob/main/specs/BUNDLE_SPEC.md
        """

        def _find_sigstore_bundle_manifest(manifests):
            for manifest in manifests:
                if manifest["artifactType"] == SIGSTORE_BUNDLE:
                    return manifest["mediaType"], manifest["digest"]

        def _get_bundle_blob_digest(layers):
            for layer in layers:
                if layer.get("mediaType") == SIGSTORE_BUNDLE:
                    return layer["digest"]

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
            raise Error("Not able to find sigstore bundle manifest info")

        bundle_manifest = self.get_manifest(
            bundle_manifest_digest, extra_headers={"Accept": bundle_manifest_mediatype}
        ).json()

        # From there, we will get the attestation in a blob.
        # It will be the first layer listed at this manifest hash location
        layers = bundle_manifest.get("layers", [])

        blob_digest = _get_bundle_blob_digest(layers)
        bundle = self.get_blob(blob_digest)
        return tag_manifest_content, bundle.content


def _write(file, content):
    file.write(content)
    file.flush()


def verify_attestation(
    registry_client: RegistryClient, image_tag: str, expected_repo: str
):
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    manifest, bundle = registry_client.get_attestation(image_tag)

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="wb") as manifest_json,
        NamedTemporaryFile(mode="wb") as bundle_json,
    ):
        _write(manifest_json, manifest)
        _write(bundle_json, bundle)

        # Call cosign with the temporary file paths
        cmd = [
            "cosign",
            "verify-blob-attestation",
            "--bundle",
            bundle_json.name,
            "--new-bundle-format",
            "--certificate-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--certificate-identity-regexp",
            f"^https://github.com/{expected_repo}/.github/workflows/release-container-image.yml@refs/heads/test/image-publication-cosign",
            manifest_json.name,
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise Exception(f"Attestation cannot be verified. {result.stderr}")
        return True


def new_version_available():
    # XXX - Implement
    return True


def check_signature(signature_bundle, pub_key):
    """Ensure that the signature bundle has been signed by the given public key."""

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="w") as signature_file,
        NamedTemporaryFile(mode="bw") as payload_file,
    ):
        json.dump(signature_bundle, signature_file)
        signature_file.flush()

        payload_bytes = b64decode(signature_bundle["Payload"])
        _write(payload_file, payload_bytes)

        cmd = [
            "cosign",
            "verify-blob",
            "--key",
            pub_key,
            "--bundle",
            signature_file.name,
            payload_file.name,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            return False
        return result.stderr == b"Verified OK\n"


def get_runtime_name() -> str:
    if platform.system() == "Linux":
        return "podman"
    return "docker"


def container_pull(image):
    cmd = [get_runtime_name(), "pull", f"{image}"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    process.communicate()


def upgrade_container_image(image, tag, pub_key, registry: RegistryClient):
    if not new_version_available():
        return

    hash = registry.get_manifest_hash(tag)
    signatures = get_signatures(image, hash)
    if len(signatures) < 1:
        raise Exception("Unable to retrieve signatures")

    print(f"Found {len(signatures)} signature(s) for {image}")
    for signature in signatures:
        signature_is_valid = check_signature(signature, pub_key)
        if not signature_is_valid:
            raise Exception("Unable to verify signature")
        print("✅ Signature is valid")

    # At this point, the signature is verified, let's upgrade
    # XXX Use the hash here to avoid race conditions
    container_pull(image)


def get_signatures(image, hash):
    """
    Retrieve the signatures from cosign download signature and convert each one to the "cosign bundle" format.
    """

    def _to_bundle(sig):
        # Convert cosign-download signatures to the format expected by cosign bundle.
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

    process = subprocess.run(
        ["cosign", "download", "signature", f"{image}@sha256:{hash}"],
        capture_output=True,
        check=True,
    )

    # XXX: Check the output first.
    signatures_raw = process.stdout.decode("utf-8").strip().split("\n")

    # Remove the last return, split on newlines, convert from JSON
    return [_to_bundle(json.loads(sig)) for sig in signatures_raw]


def parse_image_location(input_string):
    """Parses container image location into (registry, namespace, repository, tag)"""
    pattern = (
        r"^"
        r"(?P<registry>[a-zA-Z0-9.-]+)/"
        r"(?P<namespace>[a-zA-Z0-9-]+)/"
        r"(?P<repository>[^:]+)"
        r"(?::(?P<tag>[a-zA-Z0-9.-]+))?"
        r"$"
    )
    match = re.match(pattern, input_string)
    if not match:
        raise ValueError("Malformed image location")

    return (
        match.group("registry"),
        match.group("namespace"),
        match.group("repository"),
        match.group("tag") or "latest",
    )


@click.group()
def main():
    pass


@main.command()
@click.argument("image")
@click.option("--pubkey", default="pub.key")
def upgrade_image(image, pubkey):
    registry, org, package, tag = parse_image_location(image)
    registry_client = RegistryClient(registry, org, package)

    upgrade_container_image(image, tag, pubkey, registry_client)


@main.command()
@click.argument("image")
def list_tags(image):
    registry, org, package, _ = parse_image_location(image)
    client = RegistryClient(registry, org, package)
    tags = client.list_tags()
    click.echo(f"Existing tags for {client.image}")
    for tag in tags:
        click.echo(tag)


@main.command()
@click.argument("image")
@click.argument("tag")
def get_manifest(image, tag):
    registry, org, package, _ = parse_image_location(image)
    client = RegistryClient(registry, org, package)
    resp = client.get_manifest(tag, extra_headers={"Accept": OCI_IMAGE_MANIFEST})
    click.echo(resp.content)


@main.command()
@click.argument("image")
@click.option(
    "--repo",
    default=DEFAULT_REPO,
    help="The github repository to check the attestation for",
)
def attest(image: str, repo: str):
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    if shutil.which("cosign") is None:
        click.echo("The cosign binary is needed but not installed.")
        raise click.Abort()

    registry, org, package, tag = parse_image_location(image)
    tag = tag or "latest"

    client = RegistryClient(registry, org, package)
    verified = verify_attestation(client, tag, repo)
    if verified:
        click.echo(
            f"🎉 The image available at `{client.image}:{tag}` has been built by Github Runners from the `{repo}` repository"
        )


if __name__ == "__main__":
    main()
