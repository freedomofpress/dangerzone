# Contribute to Dangerzone

Dangerzone is free software, developed in the open on
[GitHub](https://github.com/freedomofpress/dangerzone). This guide shows how
to go from an idea to a merged pull request. If you haven't run Dangerzone
from source yet, start with the
[Run Dangerzone from source](../tutorials/run-dangerzone-from-source.md)
tutorial.

## Find something to work on

* Issues labelled
  [good first issue](https://github.com/freedomofpress/dangerzone/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
  are scoped for newcomers.
* Issues labelled
  [help wanted](https://github.com/freedomofpress/dangerzone/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
  are ones the maintainers would welcome a hand with.
* The [roadmap](../reference/roadmap.md) points at the milestones that show
  what is planned for the next releases, and the longer-term work.
* Documentation improvements are welcome too: every page of this site has an
  edit button that opens the source file on GitHub.

The project spans several repositories: the sandbox image, the package
repositories, the signing tooling, and more. Read
[The Dangerzone repositories](../explanation/project-repositories.md) to find
out where a change belongs, and [Code architecture](../explanation/architecture.md)
for a map of this repository.

Before starting on anything larger than a small fix, leave a comment on the
issue (or open one) so that maintainers can confirm the direction and nobody
duplicates the work.

## Set up

Follow the build guide for your platform:
[Ubuntu and Debian](build-from-source.md#debianubuntu),
[Fedora](build-from-source.md#fedora),
[macOS](build-from-source.md#macos),
[Windows](build-from-source.md#windows), or
[Qubes OS](build-from-source.md#qubes-os). Then check that the application
starts and the tests pass:

```sh
export DANGERZONE_DEV=1
poetry run dangerzone
poetry run make test
```

## Make the change

* Work on a branch off `main`.
* Keep the code style: `poetry run make lint` runs the same ruff and mypy
  checks as CI, and `poetry run make fix` applies ruff's fixes.
* Add or update tests under `tests/`. See [Run the tests](run-the-tests.md).
* If your change is visible to users, add a line to `CHANGELOG.md` under the
  `Unreleased` heading, in the matching section (`Added`, `Changed`, `Fixed`,
  `Removed`, `Platform changes`, `Development changes`), with a link to the
  issue or pull request. CI checks for this. Maintainers can add the
  `no changelog` label to pull requests that don't need an entry.
* Update the documentation in `docs/` when behaviour changes. Preview it with
  `make docs-serve` (after `poetry install --with docs`). The `--help` output
  shown in the CLI reference pages is generated from the code with
  [cog](https://cog.readthedocs.io/): run `make docs-cog` after changing a CLI
  option, CI checks that it is up to date.
* If your change touches the sandbox (the conversion code, the container
  image), it belongs in the
  [dangerzone-image](https://github.com/freedomofpress/dangerzone-image)
  repository instead.

## Send the pull request

* Write commits with a clear subject line. Squash `fixup` and `wip` commits
  before opening the pull request, CI rejects them.
* Open the pull request against `main`, explain what the change does and why,
  and link the issue it addresses (`Fixes #123`).
* CI runs the linters, the test suite on every supported platform, and builds
  packages. Address what it reports.
* A maintainer reviews the change. Reviews can take a little while, since the
  team is small and releases happen across many platforms at once.

## Test on other platforms

You don't need a machine per distribution to check your change on Debian,
Ubuntu, or Fedora: the
[containerized dev environments](dev-environments.md) build and run
Dangerzone inside a container for any supported release.

## Reporting problems instead

If you found a bug and don't plan to fix it yourself, see
[Report an issue](report-an-issue.md). For security issues, follow the
[security policy](../reference/security-policy.md).
