# Reproducible builds

We want to improve the transparency and auditability of our build artifacts, and
a way to achieve this is via reproducible builds. For a broader understanding of
what reproducible builds entail, check out https://reproducible-builds.org/.

Our build artifacts consist of:

- Container images (`amd64` and `arm64` architectures)
- macOS installers (for Intel and Apple Silicon CPUs)
- Windows installer
- Fedora packages (for regular Fedora distros and Qubes)
- Debian packages (for Debian and Ubuntu)

As of writing this, the following artifacts are reproducible:

- Container images (see [#1047](https://github.com/freedomofpress/dangerzone/issues/1047)). You can find a detailed documentation on reproducible containers in the [dangerzone-image repository](https://github.com/freedomofpress/dangerzone-image).
- Debian packages (`dangerzone` and `dangerzone-full`).

## Debian packages

Building the `.deb` files inside our pinned Debian Bookworm dev container
(`./dev_scripts/env.py --distro debian --version bookworm`) and via
`./install/linux/build-deb.py` produces byte-identical packages on every run,
given the same source tree and the same `share/container.tar`.

The mechanisms that make this work:

- **`SOURCE_DATE_EPOCH`** is pinned to the timestamp of the latest
  `debian/changelog` entry. `dpkg-source`, `dpkg-deb`, and `dh_builddeb` use
  this value for file mtimes inside the source tarball and the binary `.deb`,
  and for the `Date` field in `.changes` / `.dsc` files. The value is set by
  `debian/rules` (so it's correct even when invoking `dpkg-buildpackage`
  directly) and re-asserted by `install/linux/build-deb.py`.
- **Locale and timezone** are forced to `C.UTF-8` / `UTC`, so any tool that
  emits sorted output or formatted timestamps does so identically across
  machines.
- **File mtimes are clamped** to `SOURCE_DATE_EPOCH` after `dh_install`
  populates the staging trees. `install` and pybuild do not preserve
  timestamps, so without this step the embedded `data.tar` would carry the
  wall-clock time of the build.
- **The build environment is pinned** via the Debian Bookworm dev container,
  which fixes the versions of `dpkg`, `debhelper`, `pybuild`, and the Python
  interpreter that participate in the build.

### Verifying reproducibility

To confirm a `.deb` is reproducible, build it twice in clean environments and
compare the outputs:

```bash
# First build
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c \
    "cd dangerzone && ./install/linux/build-deb.py"
mv deb_dist deb_dist.first

# Clean and build again
git clean -fdx debian/ deb_dist/
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c \
    "cd dangerzone && ./install/linux/build-deb.py"

# Compare
sha256sum deb_dist.first/*.deb deb_dist/*.deb
# For a deeper diff if hashes differ:
#   diffoscope deb_dist.first/dangerzone_<ver>_amd64.deb deb_dist/dangerzone_<ver>_amd64.deb
```

The two sets of `.deb` files should have matching SHA-256 sums. If they don't,
`diffoscope` will show what diverged — common culprits are unpinned timestamps,
locale-dependent sort order, or files generated outside the staging trees.
