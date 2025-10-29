# Release

When confident that the release doesn't need any more changes:

- [ ] Create a PGP-signed git tag for the version, e.g., for dangerzone `v0.1.0`:

  ```bash
  git tag -s v0.1.0
  git push origin v0.1.0
  ```

- [ ] Create an archive of the Dangerzone source in `tar.gz` format:

  ```bash
  export VERSION=$(cat share/version.txt)
  git archive --format=tar.gz -o dangerzone-${VERSION:?}.tar.gz --prefix=dangerzone/ v${VERSION:?}
  ```

  _(This is covered by our automated build steps)_

- [ ] Run container scan on the produced container images (some time may have passed since the artifacts were built)

  ```bash
  docker pull anchore/grype:latest
  docker run --rm -v ./share/container.tar:/container.tar anchore/grype:latest /container.tar
  ```

- [ ] Collect the assets in a single directory, calculate their SHA-256 hashes, and sign them.
  There is an `./dev_scripts/sign-assets.py` script to automate this task.

  ```bash
  # Sign all the assets
  ./dev_scripts/sign-assets.py ~/release-assets/$VERSION/github --version $VERSION
  ```

- [ ] Upload all the assets to the draft release on GitHub.

  ```bash
  find ~/release-assets/$VERSION/github | xargs -n1 ./dev_scripts/upload-asset.py --token ~/token --draft
  ```

- [ ] Update the draft release to target the final git tag.

- [ ] Send a PR to update the [Dangerzone website](https://github.com/freedomofpress/dangerzone.rocks) to link to the new installers.

- [ ] Send a PR that updates the Dangerzone version and links to our installation instructions (`INSTALL.md`) in `README.md`

## 📣 Publish the release!

To actually publish the release:

- [ ] Merge the PRs in the [`apt-tools-prod`](https://github.com/freedomofpress/apt-tools-prod/pulls) and [`yum-tools-prod`](https://github.com/freedomofpress/yum-tools-prod/pulls) repos.
- [ ] Make the GitHub draft release public.
- [ ] Merge the PRs in [`dangerzone.rocks`](https://github.com/freedomofpress/dangerzone.rocks/pulls) and `[dangerzone](https://github.com/freedomofpress/dangerzone/pulls)`.
- [ ] Toot release announcement on our mastodon account https://social.freedom.press/@dangerzone
- [ ] Extend the `check_repos.yml` CI test for the newly added platforms, if necessary
- [ ] Manually trigger the `check_repos.yml` CI test and ensure it passes.
