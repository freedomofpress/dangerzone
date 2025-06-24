# Sandbox Release instructions

This document contains the instructions to issue a new version of the sandbox image. For more context about this, have a look at the information at `docs/developer/independent-container-updates.md`.

The release process is as follows:

0. Decide on a container image digest you want to release ;
1. Reproduce the container image on the build machines ;
2. Sign the container image on the container registry ;
3. Run the tests and ensure conversions are working properly ;
4. When ready, tag the new sandbox with the `latest` tag.

## 0. Decide on the digest you want to release

Once you know which digest you want to use, export it in a local variable so you can refer to it in the subsequent commands:

```bash
export DIGEST=<digest>
```

## 1. Reproduce the container image

You can find more information about this [in the reproducibility docs](docs/developer/reproducibility.md), that we copy here for convenience:

```bash
./dev_scripts/reproduce-image.py --debian-archive-date <date> ${DIGEST}
```

## 2. Sign and publish the remote image

Once the sandbox image has been reproduced locally, we can add a signature to the container registry:

```bash
cosign sign --recursive --sk ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST}
```

## 3. Run the tests locally

Download the sandbox image locally and run the tests:

```bash
poerty run ./dev_scripts/dangerzone-image prepare-archive
    --image ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST}
    --output share/container.tar
poetry run make test
```

## 4. Tag the sandbox

```bash
crane auth login ghcr.io -u USERNAME --password $(cat pat_token)
crane tag ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST} latest
```
