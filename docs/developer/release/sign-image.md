# Sign and release container image

Starting with Dangerzone 0.10.0, the container images that will be bundled in
our packages are no longer built in a trusted, private environment. They are
instead built nightly on GitHub actions. The maintainer is then responsible to:

1. Pick a container image for a release.
2. Reproduce it **bit-for-bit** locally.
3. Sign it with our code signing key and mark it as `latest` in ghcr.io.

> [!NOTE]
> This is the only part of the release process that maintainers can run
> independently, when they want to push out a new container image (read more in
> [Independent Container Updates](../independent-container-updates.md))

## Picking a release candidate image

Assuming that we release from the tip of the `main` branch, the maintainer
needs to:

- [ ] Go to their clone of the Dangerzone repo and pull the latest changes in the `main` branch.
- [ ] Grab the latest container image for this commit and get its digest:

  ```
  $ IMAGE=$(crane ls --full-ref $(cat share/image-name.txt) \
      | grep $(git rev-parse --short=7 HEAD) \
      | sort \
      | tail -1)
  $ IMAGE=${IMAGE%:*}@$(crane digest ${IMAGE?})
  $ echo $IMAGE
  ghcr.io/freedomofpress/dangerzone/dangerzone:20250909-0.10.0-339-g1234abcd@sha256:abcd1234...
  ```

- [ ] Ensure that this image is fresh (no more than two days old) and has been produced by a build that passes CI tests.

## Attest provenance and reproducibility

Then, the maintainer must ensure that the image has been built properly, by
attesting its provenance info and ensuring its reproducible:

- [ ] Attest provenance with `poetry run ./dev_scripts/dangerzone-image attest-provenance --commit $(git rev-parse HEAD) $IMAGE`
- [ ] Grab digests of platform-specific images with `cargo manifest $IMAGE`
- [ ] Reproduce it bit-for-bit locally for every platform:

  ```
  for platform in linux/amd64 linux/arm64; do
    poetry run ./dev_scripts/reproduce-image.py \
        --debian-archive-date <DATE> \
        --platform $platform
        ${IMAGE%@*}@sha256:<platform-digest>
  ```

## Sign and publish image

Now that we have verified that the image has been built from our nightly jobs,
and that we can reproduce it locally, we're ready to sign and publish it.

- [ ] Hop into the environment where signing keys are available, and checkout
  the https://github.com/freedomofpress/ghcr-signer repo.
- [ ] Sign the image and store the signatures locally with `uv run --recursive --sk ./ghcr-signer.py prepare "$IMAGE"`
- [ ] Prepare a PR, wait until CI passes, and then merge it
- [ ] Verify that the latest image is signed and has the expected digest:

  ```
  crane digest ghcr.io/apyrgio/dangerzone/dangerzone:latest
  cosign verify --key ... ghcr.io/apyrgio/dangerzone/dangerzone-testing:latest
  ```

At this point, the image we had chosen initially will be signed by our key, and
will be tagged as `latest`, meaning that all Dangerzone users can upgrade to it.
