# Security Policy

The Dangerzone team welcomes feedback from security researchers and the general
public to help improve our security. If you believe you have discovered a
security issue, we want to hear from you. This policy outlines steps for
reporting vulnerabilities to us, what we expect, what you can expect from us.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Our preferred communication channels are:
* **Signal:** TKTK.
* **Email:** support@dangerzone.rocks.

A member of our team should acknowledge your report **within 2 weeks**. If we
fail to do so, please use a different communication channel.

Once we have acknowledged the report, we ask for **at least 6 weeks** to
investigate, implement, and release a fix before any public disclosure, unless
we mutually agree on a different timeline. During that time we will keep you
updated as we make progress, and we will be available for any question you may
have. If we determine that a coordinated public disclosure is necessary before a
fix is ready, we will work with you on messaging and timing.

## What's in scope

Dangerzone has two main security goals:
* Malicious documents should not infect the user's device, or communicate with
  other machines.
* All metadata should be destroyed after the conversion process.

Any vulnerability that undermines these two goals **is considered critical** and
we advise you to report it via Signal. Other vulnerabilt

### About CVEs in our container image

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

If you have encountered a CVE in our container image that violates the above
policy, please report it to us.

## Security Advisories

When necessary, we have [issued CVEs](https://github.com/freedomofpress/dangerzone/security/advisories)
for Dangerzone and [security advisories](https://github.com/freedomofpress/dangerzone/tree/main/docs/advisories)
to our users. We are committed to transparency and will continue to issue
CVEs and security advisories whenever a finding warrants it.
