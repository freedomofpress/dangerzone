import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..container_utils import subprocess_run
from ..util import get_resource_path
from . import errors, log

"""
This module exposes functions to interact with the embedded cosign binary.
"""

_COSIGN_BINARY = str(get_resource_path("vendor/cosign").absolute())


def verify_local_image(oci_image_folder: Path, pubkey: Path) -> None:
    """Verify the given path against the given public key"""
    cmd = [
        _COSIGN_BINARY,
        "verify",
        "--key",
        str(pubkey),
        "--offline",
        "--local-image",
        str(oci_image_folder),
    ]
    log.debug(" ".join(cmd))
    result = subprocess_run(cmd, capture_output=True)
    if result.returncode != 0:
        log.info("Failed to verify signature", result.stderr)
        raise errors.SignatureVerificationError


def verify_blob(pubkey: Path, bundle: str, payload: str) -> None:
    cmd = [
        _COSIGN_BINARY,
        "verify-blob",
        "--key",
        str(pubkey.absolute()),
        "--bundle",
        bundle,
        payload,
    ]
    log.debug(" ".join(cmd))
    result = subprocess_run(cmd, capture_output=True)
    # If the process return code is not 0, or doesn't contain the expected
    # string, we raise an error.
    if result.returncode != 0:
        log.debug("Failed to verify signature", result)
        raise errors.SignatureVerificationError("Failed to verify signature", result)
    log.debug("Verify blob: OK")


def download_signature(image: str, digest: str) -> list[str]:
    try:
        process = subprocess_run(
            [
                _COSIGN_BINARY,
                "download",
                "signature",
                f"{image}@sha256:{digest}",
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.NoRemoteSignatures(str(e))

    # Remove the last return, split on newlines, convert from JSON
    return process.stdout.decode("utf-8").strip().split("\n")  # type:ignore[attr-defined]


def save(arch_image: str, destination: Path) -> None:
    process = subprocess_run(
        [_COSIGN_BINARY, "save", arch_image, "--dir", str(destination.absolute())],
        capture_output=True,
    )
    if process.returncode != 0:
        raise errors.AirgappedImageDownloadError()


# NOTE: You can grab the SLSA attestation for an image/tag pair with the following
# commands:
#
#     IMAGE=ghcr.io/apyrgio/dangerzone/dangerzone
#     TAG=20250129-0.8.0-149-gbf2f5ac
#     DIGEST=$(crane digest ${IMAGE?}:${TAG?})
#     ATT_MANIFEST=${IMAGE?}:${DIGEST/:/-}.att
#     ATT_BLOB=${IMAGE?}@$(crane manifest ${ATT_MANIFEST?} | jq -r '.layers[0].digest')
#     crane blob ${ATT_BLOB?} | jq -r '.payload' | base64 -d | jq
CUE_POLICY = r"""
// The predicateType field must match this string
predicateType: "https://slsa.dev/provenance/v0.2"

predicate: {{
  // This condition verifies that the builder is the builder we
  // expect and trust. The following condition can be used
  // unmodified. It verifies that the builder is the container
  // workflow.
  builder: {{
    id: =~"^https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@refs/tags/v[0-9]+.[0-9]+.[0-9]+$"
  }}
  invocation: {{
    configSource: {{
      // This condition verifies the entrypoint of the workflow.
      // Replace with the relative path to your workflow in your
      // repository.
      entryPoint: "{workflow}"

      // This condition verifies that the image was generated from
      // the source repository we expect. Replace this with your
      // repository.
      uri: =~"^git\\+https://github.com/{repository}@refs/heads/{branch}"
      // Add a condition to check for a specific commit hash
      digest: {{
        sha1: "{commit}"
      }}
    }}
  }}
}}
"""


def verify_attestation(
    image_name: str,
    branch: str,
    commit: str,
    repository: str,
    workflow: str,
) -> bool:
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    policy = CUE_POLICY.format(
        repository=repository, workflow=workflow, commit=commit, branch=branch
    )

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="w", suffix=".cue") as policy_f,
    ):
        policy_f.write(policy)
        policy_f.flush()

        # Call cosign with the temporary file paths
        cmd = [
            _COSIGN_BINARY,
            "verify-attestation",
            "--type",
            "slsaprovenance",
            "--policy",
            policy_f.name,
            "--certificate-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--certificate-identity-regexp",
            "^https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@refs/tags/v[0-9]+.[0-9]+.[0-9]+$",
            image_name,
        ]

        result = subprocess_run(cmd, capture_output=True)
        if result.returncode != 0:
            error = result.stderr.decode()  # type:ignore[attr-defined]
            raise Exception(f"Attestation cannot be verified. {error}")
        return True
