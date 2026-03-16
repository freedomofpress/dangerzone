# Security Policy

## Reporting a vulnerability

If you discover a security-related
issue, we appreciate your help in disclosing it to us in a responsible manner.

**Preferred way of disclosing security issues:**
* **GitHub:** Please use the GitHub Security Advisory
  ["Report a vulnerability"](https://github.com/freedomofpress/dangerzone/security/advisories/new)
  tab, which creates a private issue, instead of a public one.
* **Email:** Please send your report to support@dangerzone.rocks.
* **Encrypted communication:** If the finding is security-critical, you may
  request a Signal username for further communication.

We ask that you do not disclose the vulnerability publicly until we have had the
opportunity to address it.

## Security policy

Dangerzone has two main security goals:
* Malicious documents should not infect the user's device, or communicate with
  other machines.
* All metadata should be destroyed after the conversion process.

Any vulnerability that undermines these two goals **is considered critical** and
we advise you to report it via Signal.

Dangerzone uses several third-party tools to sanitize documents, such as
[LibreOffice](https://www.libreoffice.org/) and [PyMuPDF](https://pymupdf.io/).
Because these tools have a large attack surface, Dangerzone operates under the
assumption that a 0-day vulnerability probably exists for them. For this reason,
Dangerzone's primary defense is to isolate these tools within unprivileged,
networkless containers using [gVisor](https://gvisor.dev/). Read more in
[our blog](https://dangerzone.rocks/news/2024-09-23-gvisor/).

Our second line of defense is to make sure our container image is not affected
by known vulnerabilities, i.e., CVEs. We have nightly security scans for
Critical CVEs, and biweekly security scans for High CVEs. We aim for a 4 week
update cadence of our container image, or earlier, if a security finding
necessitates it.

## Security Advisories

When necessary, we have [issued CVEs](https://github.com/freedomofpress/dangerzone/security/advisories)
for Dangerzone and [security advisories](https://github.com/freedomofpress/dangerzone/tree/main/docs/advisories)
to our users. We are committed to transparency and will continue to issue
CVEs and security advisories whenever a finding warrants it.
