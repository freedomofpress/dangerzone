# First, login to the container registry.
# (We only need this because images are not publicly available yet)
# Enter "USERNAME" instead of your username
# and use your PAT as a password
# regctl registry login ghcr.io

# Get the manifest from the latest tag
regctl manifest get --format raw-body ghcr.io/freedomofpress/dangerzone/dangerzone:latest > manifest.json

# The attestation for this manifest hash is available
# at the tag named "sha256-sha256(manifest.json)"
DIGEST="sha256-$(sha256sum manifest.json | awk '{ print $1 }')"
regctl artifact get ghcr.io/freedomofpress/dangerzone/dangerzone:${DIGEST} > bundle.json

# Finally verify that the attestation is the right one
cosign verify-blob-attestation --bundle bundle.json --new-bundle-format\
       --certificate-oidc-issuer="https://token.actions.githubusercontent.com"\
       --certificate-identity-regexp="^https://github.com/freedomofpress/dangerzone/.github/workflows/release-container-image.yml@refs/heads/test/image-publication-cosign"\
       manifest.json