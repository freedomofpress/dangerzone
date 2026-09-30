# Security model

This page describes what Dangerzone promises, what it assumes, and how its defenses are layered. It is the reasoning behind the [security policy](../reference/security-policy.md), which states what we consider a reportable vulnerability.

## Goals

Dangerzone has two main security goals:

* Malicious documents should not infect the user's device, or communicate with other machines.
* All metadata should be destroyed after the conversion process.

Any vulnerability that undermines these two goals is considered critical. Everything else about Dangerzone (its usability, the quality of the output, its performance) matters, but is not a security property.

## Assumptions

Dangerzone uses several third-party tools to sanitize documents, such as [LibreOffice](https://www.libreoffice.org/) and [PyMuPDF](https://pymupdf.io/). Because these tools have a large attack surface, Dangerzone operates under the assumption that a 0-day vulnerability probably exists for them. In other words, the design does not rely on the document parsers being correct. It expects that, sooner or later, a document will take control of the process that opens it. That's why the untrusted document is only ever opened in a secure sandbox, where taking control of the process gains the attacker nothing.

Dangerzone does not use antivirus software to ensure that a file can be opened, nor does it disarm the file by removing just the "unsafe" components. First, antivirus software relies on previously seeing the same exploit in the wild, which is usually not the case for 0-days. Second, content disarm software assumes that file formats have "safe" and "unsafe" parts, and that if you snip the latter, file viewers won't have a problem with parsing the former. Our experience is that file parsers can have implementation bugs even on relatively simple parts of a specification, and that it's possible to break the readability of a file this way, leading to users opening the original.

So where does this leave us? Dangerzone's main assumption is that, at least for view purposes, documents and images can be reduced to their simplest possible representation; an RGB pixel stream per page. Reconstructing a safe PDF from such a pixel stream should then be the safest way to view this file.

## Defense in depth

**Isolation.** The parsers run inside an unprivileged, networkless container. Inside the container, they run under [gVisor](https://gvisor.dev/), an application kernel that reimplements the Linux system call interface in Go and forwards only a small, hardened set of calls to the real kernel. To reach the host, an attacker needs a working exploit for the parser, then a gVisor escape, then a container escape. Read more in [our blog](https://dangerzone.rocks/news/2024-09-23-gvisor/). On Qubes OS, the container is replaced by an offline disposable qube, which is destroyed after the conversion.

**A narrow channel.** The only thing that leaves the sandbox is a stream of page sizes and raw RGB pixels, read by Dangerzone with strict bounds (a maximum number of pages and a maximum page size). There is no file sharing and no network. The host never parses the untrusted document, and never parses anything produced by the untrusted document beyond those integers and pixel buffers.

**No network.** The sandbox has no network access, so a compromised parser cannot exfiltrate the document or fetch a second stage.

**Metadata destruction.** Rebuilding the PDF from pixels drops the original metadata as a matter of course, thus the safe PDF has no metadata in it.

**Keeping the sandbox patched.** Isolation is the primary defense, but a sandbox full of known vulnerabilities makes an attacker's job easier. Our second line of defense is to make sure our container image is not affected by known vulnerabilities, i.e., CVEs. We have nightly security scans for Critical CVEs, and biweekly security scans for High CVEs. You can see the results of our security scans in https://cves.dangerzone.rocks. We aim for a 4 week update cadence of our container image, or earlier, if a security finding necessitates it. Since 0.10.0, the sandbox image updates independently from Dangerzone releases, so a fix reaches users within days. See [Independent sandbox updates](sandbox-updates.md).

**Signed everything.** Installers and packages are signed with the release PGP key, platform code signing is applied on macOS and Windows, and the sandbox image is signed with Cosign and verified before use. See [Signing keys](../reference/signing-keys.md).

## What this model does not cover

* **A compromised host.** If your machine is already compromised, Dangerzone cannot help. Its job is to protect the host from documents.
* **Content.** The safe PDF faithfully shows what the document looked like. If the document is a phishing letter, the safe PDF is a phishing letter you can read without being exploited.
* **Availability.** A document that makes the parsers loop forever or crash results in a failed conversion, which Dangerzone reports. That is an annoyance. The host stays untouched.

## Vulnerabilities inside the sandbox

Because of the assumption above, a CVE in a tool inside the sandbox is expected and does not, on its own, compromise the security of Dangerzone. However, in combination with another more serious vulnerability (a container escape), a malicious document may be able to breach the security of Dangerzone. This is why we still publish [security advisories](../advisories/index.md) and updated sandbox images for such CVEs, and why users are advised to keep both Dangerzone and its sandbox up to date.

## Audit

Dangerzone received its [first security audit](https://freedom.press/news/dangerzone-receives-favorable-audit/) by [Include Security](https://includesecurity.com/) in December 2023. The audit was generally favorable, as it didn't identify any high-risk findings, except for 3 low-risk and 7 informational findings.

## Reporting

If you believe you have found a vulnerability, please do not report it through public GitHub issues. Follow the [security policy](../reference/security-policy.md) for the private channels and the timelines we commit to.
