# Independent Container Updates

Since version 0.9.0, Dangerzone is able to ship container images independently
from releases of the software.

One of the main benefits of doing so is to shorten the time neede to distribute the security fixes for the containers. Being the place where the actual conversion of documents happen, it's a way to keep dangerzone users secure.

If you are a dangerzone user, this all happens behind the curtain, and you should not have to know anything about that to enjoy these "in-app" updates. If you are using dangerzone in an air-gapped environment, check the sections below.

## Checking attestations

Each night, new images are built and pushed to the container registry, alongside
with a provenance attestation, enabling anybody to ensure that the image has
been originally built by Github CI runners, from a defined source repository (in our case `freedomofpress/dangerzone`).

To verify the attestations against our expectations, use the following command:
```bash
dangerzone-image attest-provenance ghcr.io/freedomofpress/dangerzone/dangerzone --repository freedomofpress/dangerzone
```

In case of sucess, it will report back:

```
🎉 Successfully verified image
'ghcr.io/freedomofpress/dangerzone/dangerzone:<tag>@sha256:<digest>'
and its associated claims:
- ✅ SLSA Level 3 provenance
- ✅ GitHub repo: freedomofpress/dangerzone
- ✅ GitHub actions workflow: <workflow>
- ✅ Git branch: <branch>
- ✅ Git commit: <commit>
```

## Sign and publish the remote image

Once the image has been reproduced locally, we can add a signature to the container registry,
and update the `latest` tag to point to the proper hash.

```bash
cosign sign --sk ghcr.io/freedomofpress/dangerzone/dangerzone:${TAG}@sha256:${DIGEST}

# And mark bump latest
crane auth login ghcr.io -u USERNAME --password $(cat pat_token)
crane tag ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:${DIGEST} latest
```

## Install updates

To check if a new container image has been released, and update your local installation with it, you can use the following commands:

```bash
dangerzone-image upgrade ghcr.io/freedomofpress/dangerzone/dangerzone
```

## Verify locally

You can verify that the image you have locally matches the stored signatures, and that these have been signed with a trusted public key:

```bash
dangerzone-image verify-local ghcr.io/freedomofpress/dangerzone/dangerzone
```

## Installing image updates to air-gapped environments

Three steps are required:

1. Prepare the archive
2. Transfer the archive to the air-gapped system
3. Install the archive on the air-gapped system

This archive will contain all the needed material to validate that the new container image has been signed and is valid.

On the machine on which you prepare the packages:

```bash
dangerzone-image prepare-archive --output dz-fa94872.tar ghcr.io/freedomofpress/dangerzone/dangerzone@sha256:<digest>
```

On the airgapped machine, copy the file and run the following command:

```bash
dangerzone-image load-archive dz-fa94872.tar
```
