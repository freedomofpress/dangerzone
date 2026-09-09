# Signing keys

Dangerzone uses several keys to sign what it ships. This page lists them so that you can cross-check fingerprints from more than one place.

## Release key (PGP)

Our binaries, source archives, container archives, and checksums are signed with a PGP key owned by Freedom of the Press Foundation.

| | |
| - | - |
| Name | Dangerzone Release Key |
| Email | `dangerzone-release-key@freedom.press` |
| Fingerprint | `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281` |
| Signing subkey | `04CA BEB5 DD76 BACF 2BD4 3D2F F3AC C60F 62EA 51CB` |
| Download | [keys.openpgp.org](https://keys.openpgp.org/vks/v1/by-fingerprint/DE28AB241FA48260FAC9B8BAA7C9B38522604281) |

The same key signs the APT and RPM repositories at `packages.freedom.press`, which is why the fingerprint above is the one to confirm when `dnf` asks `Importing GPG key 0x22604281`.

Cross-check the fingerprint with the footer of [dangerzone.rocks](https://dangerzone.rocks) and the bio of our [Mastodon account](https://fosstodon.org/@dangerzone). How to use it: [Verify PGP signatures](../how-to/install/verify-pgp-signatures.md).

## Sandbox image key (Cosign)

The sandbox container image is signed with [Cosign](https://github.com/sigstore/cosign). The public key is shipped with every Dangerzone installation as `share/freedomofpress-dangerzone.pub`, next to a detached PGP signature of it (`freedomofpress-dangerzone.pub.asc`) made with the release key above. Dangerzone verifies every sandbox image against this key before using it. See [Independent sandbox updates](../explanation/sandbox-updates.md).

Signatures are recorded in the Sigstore transparency log ([Rekor](https://docs.sigstore.dev/logging/overview/)). Dangerzone bundles and pins the Rekor public key as `share/rekor.pub`. It can be overridden with `SIGSTORE_REKOR_PUBLIC_KEY`, see [environment variables](environment-variables.md).

## Platform code signing

* **macOS**: the application bundle and `.dmg` are signed with the `Developer ID Application: Freedom of the Press Foundation (94ZZGGGJ3W)` certificate and notarized by Apple.
* **Windows**: `dangerzone.exe`, `dangerzone-cli.exe`, and the `.msi` installer are signed with an Authenticode certificate owned by Freedom of the Press Foundation.

These signatures are checked by the operating system. The PGP signatures provide an independent, second check.
