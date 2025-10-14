# Independent Container Updates

Since version 0.10.0, Dangerzone has a mechanism to auto-update the secure sandbox that is used for document conversion.

This mechanism, known as Independent Container Updates (ICU) allows us to shorten the time to patch the secure sandbox, allowing us to fix security fixes without having to do a full-blown release.

This increases the security of the conversion process dramatically, making it harder for an attacker to rely on known and patched exploits in our stack.

In order to ensure the sandbox image is trusted, we sign it with [Cosign CLI](https://github.com/sigstore/cosign), which is part of the greater [Sigstore](https://www.sigstore.dev/) ecosystem, and verify it against a key distributed in the Dangerzone application.

## Install updates

To check if a new sandbox image has been released and update your local installation with it, you can use the following command:

```bash
dangerzone-image upgrade
```

## Verify locally

You can verify that the image you have locally matches the stored signatures, and that these have been signed with a trusted public key. This is not a required step, and will be done automatically by the Dangerzone software on subsequent runs, so this command is mainly provided as a convenience.

```bash
dangerzone-image verify-local ghcr.io/freedomofpress/dangerzone/v1
```

## Checking attestations

Each night, new images are built and pushed to the container registry, alongside
with a provenance attestation, enabling anybody to ensure that the image has
been originally built by Github CI runners, from a defined source repository (in our case `freedomofpress/dangerzone`).

To verify the attestations against our expectations, use the following command:

```bash
dangerzone-image attest-provenance ghcr.io/freedomofpress/dangerzone/v1 --repository freedomofpress/dangerzone
```

In case of success, it will report back:

```
🎉 Successfully verified image
'ghcr.io/freedomofpress/dangerzone/v1:<tag>@sha256:<digest>'
and its associated claims:
- ✅ SLSA Level 3 provenance
- ✅ GitHub repo: freedomofpress/dangerzone
- ✅ GitHub actions workflow: <workflow>
```

## Installing image updates to air-gapped environments

Three steps are required:

1. Prepare the archive
2. Transfer the archive to the air-gapped system
3. Install the archive on the air-gapped system

This archive will contain all the needed material to validate that the new container image has been signed and is valid.

On the machine on which you prepare the packages (of course, adapt to the architecture you want to target):

```bash
dangerzone-image prepare-archive --arch amd64
```

On the airgapped machine, copy the file and run the following command:

```bash
dangerzone-image load-archive dangerzone-amd64.tar
```

## Configuring the verification material

Dangerzone [bundles and pins](https://github.com/freedomofpress/dangerzone/issues/1280#issuecomment-3422977474)
the public key of the [Rekor](https://docs.sigstore.dev/logging/overview/)
service, which powers the transparency log of Sigstore signatures.

If Sigstore maintainers decide to rotate this key, a new Dangerzone version will
be released, bundled with the new key. Power users can specify an updated key in
the meantime, by fetching the latest Rekor public key with:

```
$ cosign initialize
$ cat ~/.sigstore/root/tuf-repo-cdn.sigstore.dev/targets/trusted_root.json  \
    | jq -r .tlogs[0].publicKey.rawBytes \
    | base64 -d \
    | openssl pkey -pubin > rekor.pub
```

And set it with the following environment variable:

```
export SIGSTORE_REKOR_PUBLIC_KEY=rekor.pub
dangerzone
```
