import subprocess
from tempfile import NamedTemporaryFile

from . import cosign


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
      uri: =~"^git\\+https://github.com/{repo}@refs/heads/{branch}"
      // Add a condition to check for a specific commit hash
      digest: {{
        sha1: "{commit}"
      }}
    }}
  }}
}}
"""


def generate_cue_policy(repo, workflow, commit, branch):
    return CUE_POLICY.format(repo=repo, workflow=workflow, commit=commit, branch=branch)


def verify(
    image_name: str, branch: str, commit: str, repository: str, workflow: str,
) -> bool:
    """
    Look up the image attestation to see if the image has been built
    on Github runners, and from a given repository.
    """
    cosign.ensure_installed()
    policy = generate_cue_policy(repository, workflow, commit, branch)

    # Put the value in files and verify with cosign
    with (
        NamedTemporaryFile(mode="w", suffix=".cue") as policy_f,
    ):
        policy_f.write(policy)
        policy_f.flush()

        # Call cosign with the temporary file paths
        cmd = [
            "cosign",
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

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            error = result.stderr.decode()
            raise Exception(f"Attestation cannot be verified. {error}")
        return True
