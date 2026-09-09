# Independent sandbox updates

Dangerzone has a mechanism to auto-update the secure sandbox that is used for document conversion, independently from the application itself. This page explains why, and how the mechanism works. The commands are in [Update the sandbox image](../how-to/install/update-the-sandbox.md).

## Why decouple the sandbox from the application?

The sandbox image contains the tools with the largest attack surface: LibreOffice, the PDF renderer, and their dependencies. These receive security fixes quite often, and we consider them to be the most unsecure part of Dangerzone. Before independeent sandbox updates, shipping sandbox fixes meant a full Dangerzone release, which could take multiple days, if not weeks.

The independent sandbox update mechanism allows us to ship security fixes without having to do a full-blown release, shortening the time between security patches being out and the time they are used. This increases the security of the conversion process dramatically, making it harder for an attacker to rely on known and patched exploits in our stack.

## How Dangerzone learns about a new image?

Sandbox images are built and published to a container registry (`ghcr.io/freedomofpress/dangerzone/v1`) by the [dangerzone-image](https://github.com/freedomofpress/dangerzone-image) repository. When update checks are enabled, Dangerzone periodically asks the registry for the "log index" of the latest image and compares it with what it has. Then, a new image is downloaded after the user confirms (or automatically, if they asked not to be prompted again).

The image name is versioned (`v1`) so that a change in the protocol between Dangerzone and the sandbox can be shipped as `v2` without breaking older applications.

## Why you can trust a downloaded image?

Downloading executable code from the internet and running it, even inside a sandbox, deserves scrutiny. Three mechanisms make it safe:

**Signatures.** In order to ensure the sandbox image is trusted, we sign it with [Cosign](https://github.com/sigstore/cosign), which is part of the greater [Sigstore](https://www.sigstore.dev/) ecosystem, and verify it against a key distributed in the Dangerzone application (`share/freedomofpress-dangerzone.pub`). That key is itself signed with our PGP release key. Dangerzone refuses to use an image whose signature does not verify.

**Transparency log.** Cosign signatures are recorded in Rekor, Sigstore's public transparency log. Dangerzone bundles and pins the Rekor public key, and keeps track of the log index of the image it has installed. An attacker who somehow obtained a valid signature for an old, vulnerable image can't roll a user back to it: `load-archive` and the automatic updater refuse an image whose log index is lower than the installed one.

**Build attestations.** Each night, new images are built and pushed to the container registry, alongside a provenance attestation, enabling anybody to ensure that the image has been originally built by GitHub CI runners, from a defined source repository (`freedomofpress/dangerzone-image`). The images are [reproducible](reproducible-builds.md), so anyone can rebuild them and compare.

## Air-gapped machines

The sandbox with its signatures can travel on a USB stick, if required. The `dangerzone-image prepare-archive` command creates a tar file that can then be fed to  `dangerzone-image load-archive`, which will verify the signatures and the log index on the air-gapped machine before installing the image. 

## What about the application itself

The application still updates through installers and package managers. Dangerzone only notifies you when a new release is out. The reasoning for that choice, and the alternatives we considered are in listed in [Update notifications](update-notifications.md).
