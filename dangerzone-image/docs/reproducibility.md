
# Container image reproducibility

## Updating the image

The fact that our image is reproducible also means that it's frozen in time.
This means that rebuilding the image without updating our Dockerfile will result
in an image without security updates.

Here are the necessary variables that make up our image in the `Dockerfile.env`
file:

- `DEBIAN_IMAGE_DIGEST`: The index digest for the Debian container image
- `DEBIAN_ARCHIVE_DATE`: The Debian snapshot repo that we want to use
- `GVISOR_ARCHIVE_DATE`: The gVisor APT repo that we want to use
- `H2ORESTART_CHECKSUM`: The SHA-256 checksum of the H2ORestart plugin
- `H2ORESTART_VERSION`: The version of the H2ORestart plugin

If you update these values in `Dockerfile.env`, you must also create a new
Dockerfile with:

```bash
make Dockerfile
```

Updating `Dockerfile` without bumping `Dockerfile.in` is detected and should
trigger a CI error.

## Reproducing the image

For a simple way to reproduce a Dangerzone container image, you can checkout the
commit this image was built from (you can find it from the image tag in its
`g<commit>` portion), retrieve the date it was built (also included in the image
tag), and run the following command in any environment:

```bash
./utils/reproduce-image.py \
    --debian-archive-date <date> \
    <digest>
```

where:

- `<date>` should be given in YYYYMMDD format, e.g, 20250226
- `<digest>` is the SHA-256 hash of the image for the **current platform**, with
  or without the `sha256:` prefix.

This command will build a container image from the current Git commit and the
provided date for the Debian archives. Then, it will compare the digest of the
manifest against the provided one. This is a simple way to ensure that the
created image is bit-for-bit reproducible.

### Reproducing the image from its digest

If you don't have the tag of this image, and only have its digest, then it's not
straightforward to retrieve the Debian archive date and Git commit. This data is attached to the images, and can be retrieved with some external tooling (`crane` and `cosign`).

Getting the Debian archive date:

```bash
DIGEST=<digest>
LAYER=$(crane manifest ghcr.io/freedomofpress/dangerzone/v1@${DIGEST?} \
  | jq -r '.manifests[0].digest')
crane manifest ghcr.io/freedomofpress/dangerzone/v1@${LAYER?} \
  | jq -r '.annotations."rocks.dangerzone.debian_archive_date"'
```

This should return a date like `20251008`.

> [!TIP]
> You can pass the full image name and the `--debian-archive-date autodetect`
> option in the `reproduce_image.py` script, to grab the Debian archive date
> from the annotation automatically.

Getting the Git commit that the image was built from:

```bash
DIGEST=<digest>
cosign download attestation ghcr.io/freedomofpress/dangerzone/v1@${DIGEST?} \
  | jq -r '.payload' | base64 -d | jq -r '.predicate.invocation.configSource.digest.sha1'
```

This should return one or more Git commits, that at a certain date have produced
this container image. Pick any of them that you can `git switch` to.

> [!NOTE]
> It may be normal for a commit to not exist anymore, if the image was somehow
> created from a feature branch. Still, one of those commits should be part of
> the `main` branch.
