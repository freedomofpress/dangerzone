# Verifying PGP signatures

You can verify that the package you download is legitimate and hasn't been tampered with by verifying its PGP signature. For Windows and macOS, this step is optional and provides defense in depth: the Dangerzone binaries include operating system-specific signatures, and you can just rely on those alone if you'd like.

## Obtaining signing key

Our binaries are signed with a PGP key owned by Freedom of the Press Foundation:

* Name: Dangerzone Release Key
* PGP public key fingerprint `DE28 AB24 1FA4 8260 FAC9 B8BA A7C9 B385 2260 4281`
    - You can download this key [from the keys.openpgp.org keyserver](https://keys.openpgp.org/vks/v1/by-fingerprint/DE28AB241FA48260FAC9B8BAA7C9B38522604281).

_(You can also cross-check this fingerprint with the fingerprint in our [Mastodon page](https://fosstodon.org/@dangerzone) and the fingerprint in the footer of our [official site](https://dangerzone.rocks))_

You must have GnuPG installed to verify signatures. For macOS you probably want [GPGTools](https://gpgtools.org/), and for Windows you probably want [Gpg4win](https://www.gpg4win.org/).

## Signatures

Our [GitHub Releases page](https://github.com/freedomofpress/dangerzone/releases) hosts the following files:

* Windows installer (`Dangerzone-<version>.msi`)
* macOS archives (`Dangerzone-<version>-<arch>.dmg`)
* Container images (`container-<version>-<arch>.tar`)
* Source package (`dangerzone-<version>.tar.gz`)

All these files are accompanied by signatures (as `.asc` files). We'll explain how to verify them below, using `0.6.1` as an example.

## Verifying

Once you have imported the Dangerzone release key into your GnuPG keychain, downloaded the binary and ``.asc`` signature, you can verify the binary in a terminal like this:

For the Windows binary:

```bash
gpg --verify Dangerzone-0.6.1.msi.asc Dangerzone-0.6.1.msi
```

For the macOS binaries (depending on your architecture):

```bash
gpg --verify Dangerzone-0.6.1-arm64.dmg.asc Dangerzone-0.6.1-arm64.dmg
gpg --verify Dangerzone-0.6.1-i686.dmg.asc Dangerzone-0.6.1-i686.dmg
```

For the container images:

```bash
gpg --verify container-0.6.1-i686.tar.asc container-0.6.1-i686.tar
```

For the source package:

```bash
gpg --verify dangerzone-0.6.1.tar.gz.asc dangerzone-0.6.1.tar.gz
```

We also hash all the above files with SHA-256, and provide a list of these hashes as a separate file (`checksums-0.6.1.txt`). This file is signed as well, and the signature is embedded within it. You can download this file and verify it with:

```bash
gpg --verify checksums.txt
```

The expected output looks like this:

```
gpg: Signature made Mon Apr 22 09:29:22 2024 PDT
gpg:                using RSA key 04CABEB5DD76BACF2BD43D2FF3ACC60F62EA51CB
gpg: Good signature from "Dangerzone Release Key <dangerzone-release-key@freedom.press>" [unknown]
gpg: WARNING: This key is not certified with a trusted signature!
gpg:          There is no indication that the signature belongs to the owner.
Primary key fingerprint: DE28 AB24 1FA4 8260 FAC9  B8BA A7C9 B385 2260 4281
     Subkey fingerprint: 04CA BEB5 DD76 BACF 2BD4  3D2F F3AC C60F 62EA 51CB
```

If you don't see `Good signature from`, there might be a problem with the integrity of the file (malicious or otherwise), and you should not install the package.

The `WARNING:` shown above, is not a problem with the package, it only means you haven't defined a level of "trust" for Dangerzone's PGP key.

If you want to learn more about verifying PGP signatures, the guides for [Qubes OS](https://www.qubes-os.org/security/verifying-signatures/) and the [Tor Project](https://support.torproject.org/tbb/how-to-verify-signature/) may be useful.
