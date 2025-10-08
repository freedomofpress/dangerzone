# Sign and release container image

Since Dangerzone 0.10.0, container images bundled in our packages are built
nightly in GitHub Actions instead of a trusted, private environment. Releasing
the image boils down to the following steps:

1. Pick a container image for a release.
2. Reproduce it **bit-for-bit** locally.
3. Sign it with the Dangerzone signing key and mark it as `latest` in ghcr.io.

> [!NOTE]
> This is the only part of the release process that maintainers can run
> independently, when they want to push out a new container image (read more
> about [Independent Container Updates](../independent-container-updates.md))

## Pick a release candidate image

Here is how to pick a container image built from the `main` branch:

- [ ] Clone Dangerzone locally and pull the latest changes in the `main` branch.
- [ ] Grab the latest container image for this commit and get its digest:

  ```
  $ IMAGE=$(crane ls --full-ref $(cat share/image-name.txt) \
      | grep $(git rev-parse --short=7 HEAD) \
      | sort \
      | tail -1)
  $ IMAGE=${IMAGE%:*}@$(crane digest ${IMAGE?})
  $ echo $IMAGE
  ghcr.io/freedomofpress/dangerzone/v1:20250909-0.10.0-339-g1234abcd@sha256:abcd1234...
  ```

- [ ] Ensure that this image is fresh (no more than two days old) and has been produced by a build that passes CI tests.

> [!IMPORTANT]
> Do not attempt to use images created from PRs. The main issue that affects
> their reproducibility is that GitHub Actions will always internally merge the
> tip of the feature branch with the base branch, which results into a totally
> new merge commit. Always prefer images from nightly builds or workflow
> re-runs.

## Attest provenance and reproducibility

Here is how to attest the provenance info and reproducibility of the image:

- [ ] Attest provenance with `poetry run ./dev_scripts/dangerzone-image attest-provenance $IMAGE`
- [ ] Grab digests of platform-specific images (`linux/amd64` and `linux/arm64`) with `crane manifest $IMAGE`
- [ ] Reproduce it bit-for-bit locally for every platform:

  ```
  for platform in linux/amd64 linux/arm64; do
    poetry run ./dev_scripts/reproduce-image.py \
        --debian-archive-date <DATE> \
        --platform $platform
        ${IMAGE%@*}@sha256:<platform-digest>
  done
  ```

> [!NOTE]
> 1. The `DATE` argument is the ISO date that is part of the image tag. In the
>    above example, the date is `20250909`.
> 2. If the `attest-provenance` command fails, with an indication that the image
>    was built by an older commit, then there may be an explanation. If two CI
>    runs, usually within the same day, ended up building the exact same image,
>    then only one image will be pushed - the oldest one - and anecdotally one
>    attestation.

## Sign and publish image

Here is how to sign the image and push the signatures to ghcr.io:

- [ ] Clone https://github.com/freedomofpress/ghcr-signer in the environment where signing keys are present.
- [ ] Sign the image and store the signatures locally with `uv run --recursive --sk ./ghcr-signer.py prepare "$IMAGE"`
- [ ] Prepare a PR, wait until CI passes, and then merge it
- [ ] Verify that the latest image is signed and has the expected digest:

  ```
  crane digest ghcr.io/apyrgio/dangerzone/v1:latest
  cosign verify --key ... ghcr.io/apyrgio/dangerzone-testing/v1:latest
  ```

At this point, the image we had chosen initially will be signed by the
Dangerzone signing key, and will be tagged as `latest`, meaning that all
Dangerzone users will upgrade to it.
