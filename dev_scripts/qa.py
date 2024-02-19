#!/usr/bin/env python3

import abc
import argparse
import difflib
import logging
import re
import selectors
import subprocess
import sys

logger = logging.getLogger(__name__)

CONTENT_QA = r"""## QA

To ensure that new releases do not introduce regressions, and support existing
and newer platforms, we have to do the following:

- [ ] Make sure that the tip of the `main` branch passes the CI tests.
- [ ] Make sure that the Apple account has a valid application password and has
      agreed to the latest Apple terms (see [macOS release](#macos-release)
      section).
- [ ] Create a test build in Windows and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Build and run the Dangerzone .exe
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (Intel CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in macOS (M1/2 CPU) and make sure it works:
  - [ ] Check if the suggested Python version is still supported.
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create and run an app bundle.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Ubuntu LTS platform (Ubuntu 22.04
  as of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create a .deb package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Fedora platform (Fedora 39 as of
  writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Build the container image and ensure the development environment uses
    the new image.
  - [ ] Run the Dangerzone tests.
  - [ ] Create an .rpm package and install it system-wide.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below).
- [ ] Create a test build in the most recent Qubes Fedora template (Fedora 39 as
  of writing this) and make sure it works:
  - [ ] Create a new development environment with Poetry.
  - [ ] Run the Dangerzone tests.
  - [ ] Create a Qubes .rpm package and install it system-wide.
  - [ ] Ensure that the Dangerzone application appears in the "Applications"
    tab.
  - [ ] Test some QA scenarios (see [Scenarios](#Scenarios) below) and make sure
    they spawn disposable qubes.
"""

CONTENT_QA_SCENARIOS = r"""### Scenarios

#### 1. Dangerzone correctly identifies that Docker/Podman is not installed

_(Only for MacOS / Windows)_

Temporarily hide the Docker/Podman binaries, e.g., rename the `docker` /
`podman` binaries to something else. Then run Dangerzone. Dangerzone should
prompt the user to install Docker/Podman.

#### 2. Dangerzone correctly identifies that Docker is not running

_(Only for MacOS / Windows)_

Stop the Docker Desktop application. Then run Dangerzone. Dangerzone should
prompt the user to start Docker Desktop.


#### 3. Updating Dangerzone handles external state correctly.

_(Applies to Windows/MacOS)_

Install the previous version of Dangerzone, downloaded from the website.

Open the Dangerzone application and enable some non-default settings.
**If there are new settings, make sure to change those as well**.

Close the Dangerzone application and get the container image for that
version. For example:

```
$ docker images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID      CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <image ID>    <date>        <size>
```

Then run the version under QA and ensure that the settings remain changed.

Afterwards check that new docker image was installed by running the same command
and seeing the following differences:

```
$ docker images dangerzone.rocks/dangerzone:latest
REPOSITORY                   TAG         IMAGE ID        CREATED       SIZE
dangerzone.rocks/dangerzone  latest      <different ID>  <newer date>  <different size>
```

#### 4. Dangerzone successfully installs the container image

_(Linux)_

Remove the Dangerzone container image from Docker/Podman. Then run Dangerzone.
Dangerzone should install the container image successfully.

#### 5. Dangerzone retains the settings of previous runs

Run Dangerzone and make some changes in the settings (e.g., change the OCR
language, toggle whether to open the document after conversion, etc.). Restart
Dangerzone. Dangerzone should show the settings that the user chose.

#### 6. Dangerzone reports failed conversions

Run Dangerzone and convert the `tests/test_docs/sample_bad_pdf.pdf` document.
Dangerzone should fail gracefully, by reporting that the operation failed, and
showing the following error message:

> The document format is not supported

#### 7. Dangerzone succeeds in converting multiple documents

Run Dangerzone against a list of documents, and tick all options. Ensure that:
* Conversions take place sequentially.
* Attempting to close the window while converting asks the user if they want to
  abort the conversions.
* Conversions are completed successfully.
* Conversions show individual progress in real-time (double-check for Qubes).
* _(Only for Linux)_ The resulting files open with the PDF viewer of our choice.
* OCR seems to have detected characters in the PDF files.
* The resulting files have been saved with the proper suffix, in the proper
  location.
* The original files have been saved in the `unsafe/` directory.

#### 8. Dangerzone CLI succeeds in converting multiple documents

_(Only for Windows and Linux)_

Run Dangerzone CLI against a list of documents. Ensure that conversions happen
sequentially, are completed successfully, and we see their progress.

#### 9. Dangerzone can open a document for conversion via right-click -> "Open With"

_(Only for Windows, MacOS and Qubes)_

Go to a directory with office documents, right-click on one, and click on "Open
With". We should be able to open the file with Dangerzone, and then convert it.

#### 10. Dangerzone shows helpful errors for setup issues on Qubes

_(Only for Qubes)_

Check what errors does Dangerzone throw in the following scenarios. The errors
should point the user to the Qubes notifications in the top-right corner:

1. The `dz-dvm` template does not exist. We can trigger this scenario by
   temporarily renaming this template.
2. The Dangerzone RPC policy does not exist. We can trigger this scenario by
   temporarily renaming the `dz.Convert` policy.
3. The `dz-dvm` disposable Qube cannot start due to insufficient resources. We
   can trigger this scenario by temporarily increasing the minimum required RAM
   of the `dz-dvm` template to more than the available amount.
"""

CONTENT_BUILD_DEBIAN_UBUNTU = r"""## Debian/Ubuntu

Install dependencies:

<details>
  <summary><i>:memo: Expand this section if you are on Ubuntu 22.04 (Jammy).</i></summary>
  </br>

  The `conmon` version that Podman uses and Ubuntu Jammy ships, has a bug
  that gets triggered by Dangerzone
  (more details in https://github.com/freedomofpress/dangerzone/issues/685).
  If you want to run Dangerzone from source, you are advised to install a
  patched `conmon` version. A simple way to do so is to enable our
  apt-tools-prod repo, just for the `conmon` package:

  ```bash
  sudo cp ./dev_scripts/apt-tools-prod.sources /etc/apt/sources.list.d/
  sudo cp ./dev_scripts/apt-tools-prod.pref /etc/apt/preferences.d/
  ```

  Alternatively, you can install a `conmon` version higher than `v2.0.25` from
  any repo you prefer.

</details>

```sh
sudo apt install -y podman dh-python build-essential fakeroot make libqt6gui6 \
    pipx python3 python3-dev python3-stdeb python3-all
```

Install Poetry using `pipx` (recommended) and add it to your `$PATH`:

_(See also a list of [alternative installation
methods](https://python-poetry.org/docs/#installation))_

```sh
pipx ensurepath
pipx install poetry
```

After this, restart the terminal window, for the `poetry` command to be in your
`$PATH`.


Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

> **Note**: due to an issue with [poetry](https://github.com/python-poetry/poetry/issues/1917), if it prompts for your keyring, disable the keyring with `keyring --disable` and run the command again.

```
cd dangerzone
poetry install
```

Build the latest container:

```sh
python3 ./install/common/build-image.py
```

Run from source tree:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
./dev_scripts/dangerzone-cli --help

# run the GUI
./dev_scripts/dangerzone
```

Create a .deb:

```sh
./install/linux/build-deb.py
```
"""

CONTENT_BUILD_FEDORA = r"""## Fedora

Install dependencies:

```sh
sudo dnf install -y rpm-build podman python3 python3-devel python3-poetry-core \
    pipx qt6-qtbase-gui
```

Install Poetry using `pipx`:

```sh
pipx install poetry
```

Clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

> **Note**: due to an issue with [poetry](https://github.com/python-poetry/poetry/issues/1917), if it prompts for your keyring, disable the keyring with `keyring --disable` and run the command again.

```
cd dangerzone
poetry install
```

Build the latest container:

```sh
python3 ./install/common/build-image.py
```

Run from source tree:

```sh
# start a shell in the virtual environment
poetry shell

# run the CLI
./dev_scripts/dangerzone-cli --help

# run the GUI
./dev_scripts/dangerzone
```

> [!NOTE]
> Prefer running the following command in a Fedora development environment,
> created by `./dev_script/env.py`.

Create a .rpm:

```sh
./install/linux/build-rpm.py
```
"""

CONTENT_BUILD_WINDOWS = r"""## Windows

Install [Docker Desktop](https://www.docker.com/products/docker-desktop).

Install the latest version of Python 3.11 (64-bit) [from python.org](https://www.python.org/downloads/windows/). Make sure to check the "Add Python 3.11 to PATH" checkbox on the first page of the installer.


Install Microsoft Visual C++ 14.0 or greater. Get it with ["Microsoft C++ Build Tools"](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and make sure to select "Desktop development with C++" when installing.

Install [poetry](https://python-poetry.org/). Open PowerShell, and run:

```
python -m pip install poetry
```

Install git from [here](https://git-scm.com/download/win), open a Windows terminal (`cmd.exe`) and clone this repository:

```
git clone https://github.com/freedomofpress/dangerzone/
```

Change to the `dangerzone` folder, and install the poetry dependencies:

```
cd dangerzone
poetry install
```

Build the dangerzone container image:

```sh
python3 .\install\common\build-image.py
```

After that you can launch dangerzone during development with:

```
# start a shell in the virtual environment
poetry shell

# run the CLI
.\dev_scripts\dangerzone-cli.bat --help

# run the GUI
.\dev_scripts\dangerzone.bat
```
"""


class Reference:
    """Reference a Markdown section in our docs.

    This class holds a reference to a Markdown section in our docs, and compares it
    against to a stored version of this section in this file. The purpose of this class
    is to warn devs about changes in the docs that may affect the code as well. By
    having the stored doc section and the code in the same file, we limit the cases
    where those two may diverge.
    """

    REPO_URL = "https://github.com/freedomofpress/dangerzone"
    instances = []

    def __init__(self, md_path, content):
        """Initialize the class using the path for the docs and the cached section."""
        self.md_path = md_path
        self.content = content

        # Figure out the heading of the section, and the GitHub markdown anchor, from
        # the content.
        first_line = self.content.split("\n", 1)[0]
        self.heading_title = re.sub(r"^\W+", "", first_line)
        self.md_anchor = self.get_md_anchor()

        self.url = f"{self.REPO_URL}/blob/main/{self.md_path}#{self.md_anchor}"
        self.instances.append(self)

    def ensure_up_to_date(self):
        """Check if the referenced text has changed.

        This is a consistency check to ensure that the specified QA instructions in this
        script are consistent with the ones described in the docs. If the check fails,
        this file needs to be updated.
        """
        # Get section's text (as the file is now)
        with open(self.md_path, "r") as md_file:
            md_text_current = md_file.read()
            current_section_text = self.find_section_text(md_text_current)

        # Check if there have been any changes from the cached section stored in this
        # file.
        if not self.content == current_section_text:
            logger.error(
                f"The contents of section '{self.heading_title}' in file"
                f" '{self.md_path}' have changed since this file was last updated!"
            )
            logger.error("Diff follows:")
            sys.stderr.writelines(self.diff(current_section_text))
            logger.error(
                "Please ensure the instructions in this script are up"
                " to date with the respective doc section, and then update the cached"
                " section in this file."
            )
            exit(1)

    def find_section_text(self, md_text):
        """Find a section's content in a provided Markdown string."""
        start = end = None
        orig_lines = md_text.splitlines(keepends=True)
        cur_lines = self.content.splitlines(keepends=True)
        for i, line in enumerate(orig_lines):
            if line == cur_lines[0]:
                break

        start = i
        end = len(cur_lines) + i

        # Ensure that no extra content has been added in that section, until a new
        # heading begins.
        for i, line in enumerate(orig_lines[end:]):
            if orig_lines[i] and orig_lines[i][0] == "#":
                break

        end += i

        return "".join(orig_lines[start:end])

    def get_md_anchor(self):
        """Attempt to get an anchor link to the markdown section on github.

        Related: https://stackoverflow.com/questions/72536973/how-are-github-markdown-anchor-links-constructed
        """
        # Remove '#' from header
        anchor = re.sub("^[#]+", "", self.heading_title)
        # Format
        anchor = anchor.strip().lower()
        # Convert spaces to dashes
        anchor = anchor.replace(" ", "-")
        # Remove non-alphanumeric (except dash and underscore)
        anchor = re.sub("[^a-zA-Z\-_]", "", anchor)

        return anchor

    def diff(self, source):
        """Return a diff between the section in the docs and the stored one."""
        source = source.splitlines(keepends=True)
        content = self.content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            source, content, fromfile=self.md_path, tofile="qa.py"
        )
        return diff


class QABase(abc.ABC):
    """Base class for the QA tasks."""

    platforms = {}

    REF_QA = Reference("RELEASE.md", content=CONTENT_QA)
    REF_QA_SCENARIOS = Reference("RELEASE.md", content=CONTENT_QA_SCENARIOS)

    # The following class method is available since Python 3.6. For more details, see:
    # https://docs.python.org/3.6/whatsnew/3.6.html#pep-487-simpler-customization-of-class-creation
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # NOTE: Not all subclasses correspond to valid platforms. Some subclasses may
        # provide some basic functionality for an OS type or distro, but not a specific
        # version.
        if cls.get_id():
            cls.platforms[cls.get_id()] = cls

    def __init__(self, try_auto=False, skip_manual=False, debug=False):
        self.debug = debug
        self.try_auto = try_auto
        self.skip_manual = skip_manual
        self.src = (
            subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "--show-toplevel",
                ],
                stdout=subprocess.PIPE,
            )
            .stdout.decode()
            .strip("\n")
        )

    def task(*msgs, ref=None, auto=False):
        """Decorator for running a task automatically.

        This decorator does the following:
        * Check if the user has asked to run the tasks automatically.
          - If not, ask the user if they want to try it out.
          - If yes, run the task (decorated function).
        * If an exception occurs, allow the user to skip the task, or stop the
          execution.

        Args:
            msgs: A list of messages that we should show to the user, one message per
              line.
            ref: A link that can be used as a reference for a specific task.
        """

        def decorator(func):
            def inner(self, *args, **kwargs):
                # If the reference is actually defined in subclasses, grab it from
                # `self`.
                if isinstance(ref, str):
                    _ref = getattr(self, ref)
                else:
                    _ref = ref

                # Assume that the first line is the description of the task, and
                # decorate it with some "=" signs.
                dec_msgs = list(msgs)
                num_equals = (80 - 2 - len(msgs[0])) // 2 or 3
                dec_msgs.insert(0, "")
                dec_msgs[1] = "=" * num_equals + " " + msgs[0] + " " + "=" * num_equals
                self.describe(*dec_msgs, ref=_ref)

                # Handle manual tasks.
                if not auto:
                    if self.skip_manual:
                        logger.info("Skipping manual tasks, as instructed")
                        return
                    else:
                        return func(self, *args, **kwargs)

                # Detect if the task should run automatically, either because the user
                # has provided the `--try-auto` flag, or because they typed "auto" when
                # prompted.
                try_auto = False
                if self.try_auto:
                    try_auto = True
                else:
                    prompt = "Type '[a]uto' to try automatically, or '[s]kip' to skip: "
                    choice = self.prompt(
                        prompt=prompt, choices=["a", "auto", "s", "skip"]
                    )
                    try_auto = choice in ("a", "auto")

                # Run the task automatically, if the user asked to, else assume that the
                # user has run it manually.
                if try_auto:
                    logger.info("Trying automatically...")
                    out = func(self, *args, **kwargs)
                    logger.info("Completed successfully")
                    return out

            return inner

        return decorator

    def run(self, *args):
        """Run a command with extra debug logs."""
        # Construct the command line representation of the provided arguments, by taking
        # the arguments and joining them with a space character. If an argument already
        # has a space character in it, quote it before adding it to the CLI
        # representation.
        cmd_str = ""
        for arg in args:
            if " " in arg:
                cmd_str += " '" + arg + "'"
            else:
                cmd_str += " " + arg

        logger.debug("Running %s", cmd_str)
        try:
            subprocess.run(args, check=True)
            logger.debug("Successfully ran %s", cmd_str)
        except subprocess.SubprocessError:
            logger.debug("Failed to run %s", cmd_str)
            raise

    def try_run(self, *args):
        """Try to run a command and return True/False, depending on the result."""
        try:
            self.run(*args)
            return True
        except subprocess.SubprocessError:
            return False

    def describe(self, *msgs, ref=None):
        """Print a task's description.

        Log one message per line, and optionally allow a URL as a reference.
        """
        for msg in msgs:
            logger.info(msg)
        if ref:
            logger.info(
                f"For reference, see section '{ref.heading_title}' of '{ref.md_path}'"
                f" either locally, or in '{ref.url}'"
            )

    def _consume_stdin(self):
        """Consume the stdin of the process.

        Consume the stdin of the process so that stray key presses from previous steps
        do not spill over.

        It's imperative that we don't block in our attempt to consume the process'
        stdin. Typically, this requires setting the stdin file descriptor to
        non-blocking mode. However, this is not straight-forward on Windows.

        Since we don't care about consuming the file descriptor *fast*, we can create a
        tight loop that checks if the file descriptor has data to read from, and then
        read a byte (else we risk blocking). Once the file descriptor has no data to
        read, we can return.
        """
        sel = selectors.DefaultSelector()
        sel.register(sys.stdin, selectors.EVENT_READ)
        while sel.select(timeout=0):
            sys.stdin.read(1)

    def prompt(self, *msgs, ref=None, prompt=None, choices=None):
        """Print the task's description, and prompt the user for an action."""
        self.describe(*msgs, ref=ref)
        if prompt is None:
            if choices is None:
                prompt = "Press Enter once you completed this step to continue: "
            else:
                prompt = "Valid choices are %s: " % ", ".join(choices)

        if self.skip_manual:
            logger.info("Skipping manual tasks, as instructed")
            return None
        else:
            self._consume_stdin()
            # If the dev has provided a list of valid choices, do not let the prompt
            # proceed until the user has provided one of those choices.
            while True:
                choice = input(prompt)
                if not choices or choice in choices:
                    return choice

    @task("Begin the QA scenarios", ref=REF_QA_SCENARIOS)
    def qa_scenarios(self, skip=None):
        """Common prompt for the QA scenarios.

        This method suggests to the user a way to check the QA scenarios, in a
        Dangerzone environment. Then, it iterates through them, prints their
        description, and asks the user if they pass.
        """
        skip = skip or []
        self.describe(
            "You can execute into a test environment with:",
            "",
            f"    cd {self.src}",
            f"    ./dev_scripts/env.py --distro {self.DISTRO} --version"
            f" {self.VERSION} run bash",
            "",
            "and run either `dangerzone` or `dangerzone-cli`",
        )

        scenarios = [
            s[5:] for s in CONTENT_QA_SCENARIOS.splitlines() if s.startswith("#### ")
        ]

        for num, scenario in enumerate(scenarios):
            self.describe(scenario)
            if num + 1 in skip:
                self.describe("Skipping for the current platform")
            else:
                self.prompt("Does it pass?", choices=["y", "n"])
        logger.info("Successfully completed QA scenarios")

    @classmethod
    @abc.abstractmethod
    def get_id(cls):
        """Get the identifier of this class for CLI usage."""
        raise NotImplementedError("The class has not specified an identifier")

    @abc.abstractmethod
    def start(self):
        """Start the QA tests for a platform."""
        raise NotImplementedError("No steps have been defined")


# TODO: Test this class on Windows thorougly, and finish it.
class QAWindows(QABase):
    """Class for the Windows QA tasks."""

    REF_BUILD = Reference("BUILD.md", content=CONTENT_BUILD_WINDOWS)

    def _consume_stdin(self):
        # NOTE: We can't use select() on Windows. See:
        # https://docs.python.org/3/library/select.html#select.select
        import msvcrt

        while msvcrt.kbhit():
            msvcrt.getch()

    @QABase.task("Install and Run Docker Desktop", ref=REF_BUILD)
    def install_docker(self):
        logger.info("Checking if Docker Desktop is installed and running")
        if not self.try_run("docker", "info"):
            logger.info("Failed to verify that Docker Desktop is installed and running")
            self.prompt("Ensure that Docker Desktop is installed and running")
        else:
            logger.info("Verified that Docker Desktop is installed and running")

    @QABase.task(
        "Install Poetry and the project's dependencies", ref=REF_BUILD, auto=True
    )
    def install_poetry(self):
        self.run("python", "-m", "pip", "install", "poetry")
        self.run("poetry", "install")

    @QABase.task("Build Dangerzone container image", ref=REF_BUILD, auto=True)
    def build_image(self):
        self.run("python", r".\install\common\build-image.py")

    @QABase.task("Run tests", ref="REF_BUILD", auto=True)
    def run_tests(self):
        # NOTE: Windows does not have Makefile by default.
        self.run(
            "poetry", "run", "pytest", "-v", "--ignore", r"tests\test_large_set.py"
        )

    @QABase.task("Build Dangerzone .exe", ref="REF_BUILD", auto=True)
    def build_dangerzone_exe(self):
        self.run("poetry", "run", "python", r".\setup-windows.py", "build")

    @classmethod
    def get_id(cls):
        return "windows"

    def start(self):
        self.install_docker()
        self.install_poetry()
        self.build_image()
        self.run_tests()
        self.build_dangerzone_exe()


class QALinux(QABase):
    """Base class for all the Linux QA tasks."""

    REF_BUILD = None
    DISTRO = None
    VERSION = None

    def container_run(self, *args):
        """Run a command inside a Dangerzone environment."""
        self.run(
            f"{self.src}/dev_scripts/env.py",
            "--distro",
            self.DISTRO,
            "--version",
            self.VERSION,
            "run",
            "--dev",
            *args,
        )

    def shell_run(self, *args):
        """Run a shell command inside a Dangerzone environment and source dir."""
        args_str = " ".join(args)
        self.container_run("bash", "-c", f"cd dangerzone; {args_str}")

    def poetry_run(self, *args):
        """Run a command via Poetry inside a Dangerzone environment."""
        self.shell_run("poetry", "run", *args)

    @QABase.task(
        "Create Dangerzone build environment",
        "You can also run './dev_scripts/env.py ... build-dev'",
        ref="REF_BUILD",
        auto=True,
    )
    def build_dev_image(self):
        self.run(
            f"{self.src}/dev_scripts/env.py",
            "--distro",
            self.DISTRO,
            "--version",
            self.VERSION,
            "build-dev",
        )

    @QABase.task("Build Dangerzone image", ref="REF_BUILD", auto=True)
    def build_container_image(self):
        self.shell_run("python3 ./install/common/build-image.py")
        # FIXME: We need to automate this part, simply by checking that the created
        # image is in `share/image-id.txt`.
        self.prompt("Ensure that the environment uses the created image")

    @QABase.task("Run tests", ref="REF_BUILD", auto=True)
    def run_tests(self):
        self.poetry_run("make", "test")

    def build_package(self):
        """Build the Dangerzone .deb/.rpm package"""
        # Building a pakage is platform-specific, so subclasses must implement it.
        raise NotImplementedError("Building a package is not implemented")

    @QABase.task("Create Dangerzone QA environment", ref="REF_BUILD", auto=True)
    def build_qa_image(self):
        self.run(
            f"{self.src}/dev_scripts/env.py",
            "--distro",
            self.DISTRO,
            "--version",
            self.VERSION,
            "build",
            "--download-pyside6",
        )

    @classmethod
    def get_id(cls):
        """Return the ID for the QA class.

        If the QA class is a base one, then either the distro or the version will be
        None. In this case, return None as well, to signify that this class does not
        correspond to a specific platform."""
        if not cls.DISTRO or not cls.VERSION:
            return None
        else:
            return f"{cls.DISTRO}-{cls.VERSION}"

    def start(self):
        self.build_dev_image()
        self.build_container_image()
        self.run_tests()
        self.build_package()
        self.build_qa_image()
        self.qa_scenarios(skip=[1, 2, 8, 9])


class QADebianBased(QALinux):
    """Base class for Debian-based distros.

    This class simply points to the proper build instructions, and builds the Debian
    package.
    """

    REF_BUILD = Reference("BUILD.md", content=CONTENT_BUILD_DEBIAN_UBUNTU)

    @QABase.task("Build .deb", ref=REF_BUILD, auto=True)
    def build_package(self):
        self.shell_run("./install/linux/build-deb.py")


class QADebianBullseye(QADebianBased):
    DISTRO = "debian"
    VERSION = "bullseye"


class QADebianBookworm(QADebianBased):
    DISTRO = "debian"
    VERSION = "bookworm"


class QADebianTrixie(QADebianBased):
    DISTRO = "debian"
    VERSION = "trixie"


class QAUbuntu2004(QADebianBased):
    DISTRO = "ubuntu"
    VERSION = "20.04"


class QAUbuntu2204(QADebianBased):
    DISTRO = "ubuntu"
    VERSION = "22.04"


class QAUbuntu2310(QADebianBased):
    DISTRO = "ubuntu"
    VERSION = "23.10"


class QAFedora(QALinux):
    """Base class for Fedora distros.

    This class simply points to the proper build instructions, and builds the RPM
    package.
    """

    DISTRO = "fedora"
    REF_BUILD = Reference("BUILD.md", content=CONTENT_BUILD_FEDORA)

    @QABase.task("Build .rpm", ref=REF_BUILD, auto=True)
    def build_package(self):
        self.container_run(
            "./dangerzone/install/linux/build-rpm.py",
        )


class QAFedora39(QAFedora):
    VERSION = "39"


class QAFedora38(QAFedora):
    VERSION = "38"


def parse_args():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Run QA tests for a platform",
    )
    parser.add_argument(
        "platform",
        choices=sorted(QABase.platforms.keys()),
        help="Run QA tests for the provided platform",
        nargs="?",
    )
    parser.add_argument(
        "--try-auto",
        action="store_true",
        default=False,
        help="Try to run the automated parts of the QA steps",
    )
    # FIXME: Find a better way to skip tasks in non-interactive environments, while
    # retaining the ability to be semi-prompted in interactive environments.
    parser.add_argument(
        "--skip-manual",
        action="store_true",
        default=False,
        help="Skip the manual parts of the QA steps",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logs",
    )
    parser.add_argument(
        "--check-refs",
        action="store_true",
        default=False,
        help="Check if references to docs still hold",
    )

    args = parser.parse_args()

    if not args.check_refs and not args.platform:
        parser.print_help(sys.stderr)
        exit(1)

    return args


def setup_logging(debug=False):
    """Simple way to setup logging.

    Copied from: https://docs.python.org/3/howto/logging.html
    """
    # specify level
    if debug:
        lvl = logging.DEBUG
    else:
        lvl = logging.INFO

    logging.basicConfig(
        level=lvl,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    args = parse_args()
    setup_logging(args.debug)

    for ref in Reference.instances:
        ref.ensure_up_to_date()
    if args.check_refs:
        return

    try:
        qa_cls = QABase.platforms[args.platform]
    except KeyError:
        raise RuntimeError("Unexpected platform: %s", args.platform)

    logger.info("Starting QA tests for %s", args.platform.capitalize())
    qa_cls(args.try_auto, args.skip_manual, args.debug).start()
    logger.info("Successfully completed QA tests for %s", args.platform.capitalize())


if __name__ == "__main__":
    sys.exit(main())
