# Reference

Reference pages describe the machinery: what the tools accept, what the
settings mean, what we support. They are meant to be consulted, and they stay
neutral: no instructions, no opinions. For those, see the
[how-to guides](../how-to/index.md) and the
[explanation](../explanation/index.md) section.

## Platforms and formats

* [Supported platforms](supported-platforms.md): operating systems and
  releases we support, and how each is tested.
* [Supported document formats](supported-formats.md): what Dangerzone can
  convert.

## Command-line tools

* [dangerzone-cli](cli/dangerzone-cli.md): convert documents from a terminal.
* [dangerzone-image](cli/dangerzone-image.md): manage the sandbox image.
* [dangerzone-machine](cli/dangerzone-machine.md): manage the Podman machine
  on macOS and Windows.

* [Sandbox protocol](sandbox-protocol.md): the interface between the host
  and the conversion sandbox, including container flags and exit codes.

## Configuration

* [Settings](settings.md): the `settings.json` file and every key in it.
* [Environment variables](environment-variables.md): variables that change
  how Dangerzone behaves, mostly for development.

## Security

* [Signing keys](signing-keys.md): the PGP and Cosign keys that sign our
  releases and sandbox images.
* [Security policy](security-policy.md): how to report a vulnerability and
  what we consider in scope.
* [Security advisories](../advisories/index.md): past advisories.

## Project

* [Changelog](changelog.md)
* [Third-party notice](third-party-notice.md)
* [License](license.md)
* [Roadmap](roadmap.md): the milestones that track what comes next.
