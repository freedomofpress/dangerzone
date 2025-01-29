import subprocess
from tempfile import NamedTemporaryFile

from .utils import write


def verify_attestation(
    manifest: bytes, attestation_bundle: bytes, image_tag: str, expected_repo: str
):
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="wb") as manifest_json,
        NamedTemporaryFile(mode="wb") as attestation_bundle_json,
    ):
        write(manifest_json, manifest)
        write(attestation_bundle_json, attestation_bundle)

        # Call cosign with the temporary file paths
        cmd = [
            "cosign",
            "verify-blob-attestation",
            "--bundle",
            attestation_bundle_json.name,
            "--new-bundle-format",
            "--certificate-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--certificate-identity-regexp",
            f"^https://github.com/{expected_repo}/.github/workflows/release-container-image.yml@refs/heads/test/image-publication-cosign",
            manifest_json.name,
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error = result.stderr.decode()
            raise Exception(f"Attestation cannot be verified. {error}")
        return True
