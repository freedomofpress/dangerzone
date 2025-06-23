# Pre-release

Here is a list of tasks that should be done before issuing the release. They can
run from the developer's laptop and are not tied to any build environment.

- [ ] Create a new issue named **QA and Release for version \<VERSION\>**, to track the general progress.
      You can generate its content with the `poetry run ./dev_scripts/generate-release-tasks.py` command.
- [ ] [Add new Linux platforms and remove obsolete ones](#add-new-linux-platforms-and-remove-obsolete-ones)
- [ ] Bump the Python dependencies using `poetry lock`
- [ ] Bump the GitHub asset dependencies using `poetry run mazette lock`
- [ ] Check for new [WiX releases](https://github.com/wixtoolset/wix/releases) and update it if needed
- [ ] Update `version` in `pyproject.toml`
- [ ] Update `share/version.txt`
- [ ] Update the "Version" field in `install/linux/dangerzone.spec`
- [ ] Bump the Debian version by adding a new changelog entry in `debian/changelog`
- [ ] [Bump the minimum Docker Desktop versions](#bump-the-minimum-docker-desktop-version) in `isolation_provider/container.py`
- [ ] Bump the dates and versions in the `Dockerfile.env`
- [ ] Bump the bundled log index in `dangerzone/updater/signatures.py` with the log index of the bundled sandbox.
- [ ] Update the download links in our `INSTALL.md` page to point to the new version (the download links will be populated after the release)
- [ ] Update screenshot in `README.md`, if necessary
- [ ] CHANGELOG.md should be updated to include a list of all major changes since the last release
- [ ] A draft release should be created. Copy the release notes text from the template at [`docs/templates/release-notes`](https://github.com/freedomofpress/dangerzone/tree/main/docs/templates/)
- [ ] Send the release notes to editorial for review
- [ ] Tag the tip of the `main` branch as `v<version>-rc1`. E.g. `git tag -s v0.9.1-rc1`.

## Add new Linux platforms and remove obsolete ones

Our currently supported Linux OSes are Debian, Ubuntu, Fedora (we treat Qubes OS
as a special case of Fedora, release-wise). For each of these platforms, we need
to check if a new version has been added, or if an existing one is now EOL
(https://endoflife.date/ is handy for this purpose).

In case of a new version (beta, RC, or official release):

1. Add it in our CI workflows, to test if that version works.
   - See `.circleci/config.yml` and `.github/workflows/ci.yml`, as well as
     `dev_scripts/env.py` and `dev_scripts/qa.py`.
2. Do a test of this version locally with `dev_scripts/qa.py`. Focus on the
   GUI part, since the basic functionality is already tested by our CI
   workflows.
3. Add the new version in our `INSTALL.md` document, and drop a line in our
   `CHANGELOG.md`.
4. If that version is a new stable release, update the `RELEASE.md` and
   `BUILD.md` files where necessary.
5. Send a PR with the above changes.

In case of the removal of a version:

1. Remove any mention to this version from our repo.
   - Consult the previous paragraph, but also `grep` your way around.
2. Add a notice in our `CHANGELOG.md` about the version removal.

## Bump the minimum Docker Desktop version

We embed the minimum docker desktop versions inside Dangerzone, as an incentive for our macOS and Windows users to upgrade to the latest version.

You can find the latest version at the time of the release by looking at [their release notes](https://docs.docker.com/desktop/release-notes/)
