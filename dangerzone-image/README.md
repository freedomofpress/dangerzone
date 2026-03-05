# Dangerzone-image

This repository contains the dangerzone container image that is used to perform "document to pixels" conversions. This container is used by [dangerzone](https://dangerzone.rocks) to do the secure conversions of the documents.

## Using the container image

The image is published on a monthly basis on the container registry, alongside their Cosign signatures.

```
ghcr.io/freedomofpress/dangerzone/v1
```

## dangerzone-docs-to-pixels python package

The code that runs inside the container is packaged under the name "dangerzone-insecure-conversion".
This is considered insecure because it doesn't run by default inside a sandbox.