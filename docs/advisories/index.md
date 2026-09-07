# Security advisories

When necessary, we issue security advisories to our users, in addition to
[CVEs](https://github.com/freedomofpress/dangerzone/security/advisories) on
GitHub. Advisories are published here and linked from the release notes of
the release that addresses them.

Vulnerabilities in the tools inside the sandbox are expected. On their own
they do not compromise Dangerzone, since the sandbox contains them. We still
publish advisories and updated sandbox images for them, so that a second
vulnerability (a sandbox escape) can't be combined with a known one. See
[Security model](../explanation/security-model.md).

| Date | Summary | Fixed in |
| ---- | ------- | -------- |
| [2024-12-24](2024-12-24.md) | gst-plugins-base vulnerabilities (CVE-2024-47538, CVE-2024-47607, CVE-2024-47615) inside the sandbox | 0.8.1 |
| [2023-12-07](2023-12-07.md) | GhostScript vulnerability (CVE-2023-43115) inside the sandbox | 0.5.1 |
| [2023-10-25](2023-10-25.md) | Missing `default_dispvm` setting in the Qubes OS installation instructions | Configuration change |

To report a vulnerability, follow the [security policy](../reference/security-policy.md).
