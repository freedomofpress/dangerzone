# Run Dangerzone from source

This tutorial walks you through a first development setup: you will clone the repository, install the dependencies, run the application and its test suite from the source tree, and make a small change to see it live. It follows a single path, on Ubuntu or Debian, so that every step is predictable. The [build from source](../how-to/contribute/build-from-source.md#debianubuntu) how-to guides cover the other platforms and the packaging steps.

You need a Debian or Ubuntu machine (a virtual machine will only work if you can do nested virtualization), `sudo` access, about 5 GB of free disk space, and an internet connection.

## 1. Install the system dependencies

```sh
sudo apt install -y podman dh-python build-essential make libqt6gui6 \
    pipx python3 python3-dev
```

Podman runs the sandbox. The Qt library is needed by the graphical application. `pipx` is used in the next step.

??? note "Ubuntu 22.04 (Jammy) users"

    The `conmon` version that Podman uses and Ubuntu Jammy ships has a bug that gets triggered by Dangerzone (more details in [#685](https://github.com/freedomofpress/dangerzone/issues/685)). Install a patched `conmon` before continuing, as described in the [Ubuntu and Debian build guide](../how-to/contribute/build-from-source.md#debianubuntu).

## 2. Install Poetry

Dangerzone manages its Python dependencies with [Poetry](https://python-poetry.org/):

```sh
pipx ensurepath
pipx install poetry
pipx inject poetry poetry-plugin-export
```

Close and reopen your terminal so that `poetry` is on your `PATH`, then check:

```console
$ poetry --version
Poetry (version 2.x)
```

## 3. Clone the repository and install the Python dependencies

```sh
git clone https://github.com/freedomofpress/dangerzone/
cd dangerzone
poetry install
```

!!! note

    If Poetry prompts for your keyring, disable it with `keyring --disable` and run `poetry install` again. This is a known [Poetry issue](https://github.com/python-poetry/poetry/issues/1917).

## 4. Download the assets and the sandbox image

Dangerzone depends on a few binaries and external resources. Fetch them with:

```sh
poetry run mazette install
```

Then fetch the latest sandbox image and store it where the development build expects it:

```sh
export DANGERZONE_DEV=1
poetry run dangerzone-image prepare-archive --output share/container.tar
```

`DANGERZONE_DEV=1` tells Dangerzone that it runs from a source tree, so it looks for resources under `share/` instead of the system paths. Keep it set for the rest of this tutorial.

## 5. Run the application

Start the graphical application:

```sh
poetry run dangerzone
```

The main window appears. Convert a document if you like, following [Convert your first document](convert-your-first-document.md), then close the window.

The command-line tool works the same way:

```sh
poetry run dangerzone-cli --help
```

## 6. Run the tests

```sh
poetry run make test
```

The suite contains tests for the CLI, the GUI (headless), and the isolation providers. It takes a few minutes and ends with a summary of passed tests. Some tests convert sample documents from `tests/test_docs/` through the real sandbox, so Podman has to work on your machine for the suite to pass.

## 7. Make a change and see it

Open `dangerzone/gui/main_window.py` and find the label of the button that selects documents:

```python
self.dangerous_doc_button = QtWidgets.QPushButton("Select suspicious documents ...")
```

Change the text to anything you would like, save, and start the application again with `poetry run dangerzone`. The button now shows your text: the application runs straight from the source tree, so there is no build step between an edit and a run.

Revert the change with `git checkout dangerzone/gui/main_window.py` when you are done.

## What you learned

You now have a working development environment: `poetry run dangerzone` starts the app, `poetry run make test` runs the tests, and `DANGERZONE_DEV=1` points Dangerzone at the resources in `share/`.

## Where to go next

* Lint and format like CI does with `poetry run make lint` and `poetry run make fix`.
* Build a `.deb` package from your checkout: [Build from source on Ubuntu and Debian](../how-to/contribute/build-from-source.md#debianubuntu).
* Test in a containerized environment for another distribution (Fedora, or older Ubuntu and Debian): [Use the containerized dev environments](../how-to/contribute/dev-environments.md).
* Read how the pieces fit together: [How Dangerzone works](../explanation/how-dangerzone-works.md).
