# Using the Doit Automation Tool

Developers can use the [Doit](https://pydoit.org/) automation tool to create
release artifacts. The purpose of the tool is to automate the manual release
instructions in `RELEASE.md` file. Not everything is automated yet, since we're
still experimenting with this tool. You can find our task definitions in this
repo's `dodo.py` file.

## Why Doit?

We picked Doit out of the various tools out there for the following reasons:

* **Pythonic:** The configuration file and tasks can be written in Python. Where
  applicable, it's easy to issue shell commands as well.
* **File targets:** Doit borrows the file target concept from Makefiles. Tasks
  can have file dependencies, and targets they build. This makes it easy to
  define a dependency graph for tasks.
* **Hash-based caching:** Unlike Makefiles, doit does not look at the
  modification timestamp of source/target files, to figure out if it needs to
  run them.  Instead, it hashes those files, and will run a task only if the
  hash of a file dependency has changed.
* **Parallelization:** Tasks can be run in parallel with the `-n` argument,
  which is similar to `make`'s `-j` argument.

## How to Doit?

Make sure that your environment is clean, and you have ample disk space. You
can run:

```bash
uv run doit clean --dry-run  # if you want to see what would happen
uv run doit clean  # you'll be asked to cofirm that you want to clean everything
```

Finally, you can build all the release artifacts with `doit`, or a specific task
with:

```
uv run doit <task>
```

## Tips and tricks

* You can run `uv run doit list --all -s` to see the full list of tasks, their
  dependencies, and whether they are up to date.
* You can run `uv run doit info <task>` to see which dependencies are missing.
* You can change this line in `pyproject.toml` to `true`, to allow using the
  Docker/Podman build cache:

  ```
  use_cache = true
  ```

  > [!WARNING]
  > Using caching may speed up image builds, but is not suitable for release
  > artifacts. The ID of our base container image (Alpine Linux) does not change
  > that often, but its APK package index does. So, if we use caching, we risk
  > skipping the `apk upgrade` layer and end up with packages that are days
  > behind.

* You can pass the following environment variables to the script, in order to
  affect some global parameters:
  - `CONTAINER_RUNTIME`: The container runtime to use. Either `podman` (default)
    or `docker`.
  - `RELEASE_DIR`: Where to store the release artifacts. Default path is
    `~/release-assets/<version>`
  - `APPLE_ID`: The Apple ID to use when signing/notarizing the macOS DMG.
