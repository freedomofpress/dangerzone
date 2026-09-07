# Release a new version

The documents in this section are targeted towards Dangerzone release managers
who want to publish a new Dangerzone release. If you are looking for a way to
run Dangerzone from source, please check the
[build from source](../build-from-source.md#debianubuntu) guides instead.

Having a new Dangerzone release out is a rather involved process, because you
have to do so simultaneously for all the distributions we support. Based on the
experience from past releases, a large list of steps to follow has been assembled.

So, it's either boring uneventful releases or gung-ho brittle ones. Pick
your poison (the first one).

This list is broken down in the following phases:

1. [Pre-release](pre-release.md)
2. [Prepare build environments](prepare-build-envs.md)
3. [Sign and release container image ↗️](https://github.com/freedomofpress/dangerzone-image/blob/main/docs/sign-image.md)
4. [Build release artifacts](build.md)
5. [QA](qa.md)
6. [Release](release.md)

The checkboxes in these pages can be turned into a tracking issue with
`poetry run ./dev_scripts/generate-release-tasks.py`. The
[release notes templates](release-notes-templates.md) provide the text for the
GitHub release.
