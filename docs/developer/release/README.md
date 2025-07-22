# Release instructions

The documents in this directory are targeted towards Dangerzone release managers
who want to publish a new Dangerzone release. If you are looking for a way to
run Dangerzone from source, please check [`BUILD.md`](../../../BUILD.md) instead.

Having a new Dangerzone release out is a rather involved process, because you
have to do so simultaneously for all the distros that we support. Based on the
experience from past releases, we have assembled a large list of steps to
follow. So, it's either boring uneventful releases or gung-ho brittle ones. Pick
your poison (the first one).

This list is broken down in the following phases:

1. [Pre-release](pre-release.md)
2. [Prepare build environments](prepare-build-envs.md)
3. [Build release artifacts](build.md)
4. [QA](qa.md)
5. [Release](release.md)

The phases are broken down in a way that if QA fails (4), the devs need to make
changes to the codebase and then go back to building the release artifacts (3).
