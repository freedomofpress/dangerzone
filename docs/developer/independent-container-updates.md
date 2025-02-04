# Independent Container Updates

Since version 0.9.0, Dangerzone is able to ship container images independently
from issuing a new release of the software.

This is useful as images need to be kept updated with the latest security fixes.

## Nightly images and attestations

Each night, new images are built and pushed to our container registry, alongside
with a provenance attestation, enabling anybody to ensure that the image has
been originally built by Github CI runners, from a defined source repository (in our case `freedomofpress/dangerzone`).

To verify the attestations against our expectations, use the following command:
```bash
poetry run ./dev_scripts/registry.py attest ghcr.io/freedomofpress/dangerzone/dangerzone:latest --repo freedomofpress/dangerzone
```

In case of sucess, it will report back:

```
🎉 The image available at `ghcr.io/freedomofpress/dangerzone/dangerzone:latest` has been built by Github runners from the `freedomofpress/dangerzone` repository.
```

## Container updates on air-gapped environments

In order to make updates on an air-gapped environment, you will need to prepare an archive for the air-gapped environment. This archive will contain all the needed material to validate that the new container image has been signed and is valid.

On the machine on which you prepare the packages:

```bash
dangerzone-image prepare-archive ghcr.io/almet/dangerzone/dangerzone@sha256:fa948726aac29a6ac49f01ec8fbbac18522b35b2491fdf716236a0b3502a2ca7
```

On the airgapped machine, copy the file and run the following command:

```bash
dangerzone-image load-archive 
```