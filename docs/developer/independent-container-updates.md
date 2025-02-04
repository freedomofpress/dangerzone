# Independent Container Updates

Since version 0.9.0, Dangerzone is able to ship container images independently
from releases.

One of the main benefits of doing so is to lower the time needed to patch security issues inside the containers.

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
'ghcr.io/apyrgio/dangerzone/dangerzone:20250129-0.8.0-149-gbf2f5ac@sha256:4da441235e84e93518778827a5c5745d532d7a4079886e1647924bee7ef1c14d'
and its associated claims:
- ✅ SLSA Level 3 provenance
- ✅ GitHub repo: apyrgio/dangerzone
- ✅ GitHub actions workflow: .github/workflows/multi_arch_build.yml
- ✅ Git branch: test/multi-arch
- ✅ Git commit: bf2f5accc24bd15a4f5c869a7f0b03b8fe48dfb6
```

## Install updates

To check if a new container image has been released, and update your local installation with it, you can use the following commands:

```bash
dangerzone-image upgrade ghcr.io/almet/dangerzone/dangerzone
```

## Verify locally

You can verify that the image you have locally matches the stored signatures, and that these have been signed with a trusted public key:

```bash
dangerzone-image verify-local ghcr.io/almet/dangerzone/dangerzone
```

## Air-gapped environments

In order to make updates on an air-gapped environment, you will need to prepare an archive for the air-gapped environment. This archive will contain all the needed material to validate that the new container image has been signed and is valid.

On the machine on which you prepare the packages:

```bash
dangerzone-image prepare-archive --output dz-fa94872.tar ghcr.io/almet/dangerzone/dangerzone@sha256:fa948726aac29a6ac49f01ec8fbbac18522b35b2491fdf716236a0b3502a2ca7
```

On the airgapped machine, copy the file and run the following command:

```bash
dangerzone-image load-archive dz-fa94872.tar
```
