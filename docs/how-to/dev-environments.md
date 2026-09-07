# Use the containerized dev environments

The `dev_scripts/env.py` script creates environments where a user can run
Dangerzone, allows the user to run arbitrary commands in these environments, as
well as run Dangerzone (nested containerization). Use it to build packages for,
or test on, a Linux distribution other than the one on your machine. For the
design and the caveats behind these environments, see
[Development environments](../explanation/development-environments.md).

For the full usage information, run `./dev_scripts/env.py --help`.

## Pick an environment type

The script supports two types of environments, a *dev* environment with the
developer tools baked in and the source tree mounted, and an *end-user*
environment with only Dangerzone installed from a `.deb`/`.rpm` (or from our
QA or production repositories with `--qa` / `--prod`). They are described in
[Create Dangerzone environments](../explanation/development-environments.md).
Each environment corresponds to a Dockerfile, which is generated on the fly.
The developer can see this Dockerfile by passing `--show-dockerfile`.

## Build and enter a dev environment

```bash
./dev_scripts/env.py --distro debian --version bookworm build-dev
./dev_scripts/env.py --distro debian --version bookworm run --dev bash
```

Inside the shell, the source tree is at `/home/user/dangerzone`, so the usual
commands work:

```bash
cd dangerzone
poetry run mazette install
poetry run dangerzone-image prepare-archive --output share/container.tar
poetry run make test
```

Replace `--distro debian --version bookworm` with, for example,
`--distro fedora --version 44` or `--distro ubuntu --version noble`.

## Run a single command

You can also run one command and get its exit status, which is how the release
instructions build packages:

```bash
./dev_scripts/env.py --distro debian --version bookworm run --dev bash -c \
    "cd dangerzone && ./install/linux/build-deb.py"
```

## Build and enter an end-user environment

Build a `.deb` or `.rpm` first (it is picked up from `deb_dist/` or `dist/`),
then:

```bash
./dev_scripts/env.py --distro fedora --version 44 build
./dev_scripts/env.py --distro fedora --version 44 run bash
```

Add `--qa` or `--prod` to `build` to install the package from our QA or
production repositories instead, and `--full` to install the `dangerzone-full`
variant with the bundled container.

The environments are containers with the X11 socket mounted, so `dangerzone`
opens its window on your desktop. Containers are deleted when the command
exits, so anything you change inside is lost, on purpose.
