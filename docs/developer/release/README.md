# Release instructions

The documents in this directory are targeted towards Dangerzone release managers
who want to publish a new Dangerzone release. If you are looking for a way to
run Dangerzone from source, please check [`BUILD.md`](../../../BUILD.md) instead.

Having a new Dangerzone release out is a rather involved process, because you
have to do so simultaneously for all the distributions we support. Based on the
experience from past releases, a large list of steps to follow has been assembled.

So, it's either boring uneventful releases or gung-ho brittle ones. Pick
your poison (the first one).

This list is broken down in the following phases:

1. [Pre-release](pre-release.md)
2. [Prepare build environments](prepare-build-envs.md)
3. [Sign and release container image](sign-image.md)
4. [Build release artifacts](build.md)
5. [QA](qa.md)
6. [Release](release.md)
