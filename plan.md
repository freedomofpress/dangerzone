The issue #1171, "Let Dangerzone control the lifecycle of a Podman machine,"
(https://github.com/freedomofpress/dangerzone/issues/1171)
proposes that Dangerzone should manage its own Podman machine. This includes
machine initialization, user feedback during initialization, cleanup of older
machines, and a new dangerzone-machine CLI command.

Suggested Plan for Implementation:

This plan breaks down the implementation into manageable phases:
* First phase creates a Python module in Dangerzone for handling Podman machines.
* Second phase exposes this Python module from a CLI.
* Third phase adds a bottom bar in the Dangerzone GUI that informs the user
  about background tasks.
* Fourth phase moves the existing upgrade / image loading logic into a
  background task.
* Fifth phase makes the background task update the bottom bar.
* Sixth phase makes conversions block until the background task is done.
* Seventh phase adds a way to initialize and start Podman machines in the
  background tasks
* Eighth phase allows a user to see logs of the background task.
* Ninth phase makes the solution more robust code-wise and UX-wise.
* Tenth phase updates the documentation and user-facing docs.

## Core requirements

* A success criteria at the end of each phase is to accompany the code by
  unit tests. The unit tests must pass in order to complete the phase.
* The tests can run with `poetry run pytest`. If it fails, ensure that `poetry
  sync` works.
* Unit tests should use `pytest-subprocess` to unit test commands, or
  `pytest-qt` to unit test GUI code.
* Changes must be committed between each phase.
* The produced Python code must be able to run on Windows, Linux, and macOS
  systems. This means that paths must be defined as `Path("dir") / "name"` and
  not `Path("dir/name")`.
* Use click instead of argparse for building CLIs.

## Phase 1: Core Podman Machine Management

1. Read the `dangerzone/podman` module, which contains a Python wrapper for
   Podman commands. More specifically, it includes the necessary code to manage
   Podman machines, and connect to them.
2. Create a `dangerzone/podman/machine.py` Python module: Create a new module
   `dangerzone/podman/machine.py` to encapsulate all Podman machine lifecycle
   logic. Core requirements of this module:
   * It should prefix Podman machines with a unique prefix `dz-internal-`
   * The suffix should be the Dangerzone version, obtained via
     `dangerzone.util.get_version()`.
   * It installs WSL2 in the user's laptop, if not already installed. On Windows
     11, one suggestion is to use:

     ```
     wsl --update
     wsl --install --no-distribution
     ```

     If the WSL2 init fails, the job should fail.
   * It creates and passes to Podman invocations a temporary `containers.conf`
     file that sets:

     ```
     helper_binaries_dir=["/path/to/share/vendor/podman"]
     ```

     - The path to `share/vendor/podman` should be obtained dynamically using
       `dangerzone.util.get_resource_path("share/vendor/podman")`.
   * It should detect if a machine exists, before initializing it.
   * If a machine with `dz-internal-` prefix exists, but with an incorrect
     version (exact match), it should remove it.
   * It should initialize the Podman machine using a local image:
     `share/machine.tar`. It can use the `image` argument of
     `PodmanCommand.machine.init()` for that. The path to `share/machine.tar`
     should be obtained dynamically using
     `dangerzone.util.get_resource_path("share/machine.tar")`.
3. It supports the following actions for controlling the lifecycle of a Podman
   machine, and uses the Python wrapper in `dangerzone/podman/command/`:
   * Create machine, via `PodmanCommand.machine.init` (passing `cpus=`,
     `memory=`, `timezone=` arguments as needed).
   * Start machine, via `PodmanCommand.machine.start`
   * Stop machine, via `PodmanCommand.machine.stop`
   * Remove machine, via `PodmanCommand.machine.remove`
   * Reset machines, via `PodmanCommand.machine.reset`
   * List Dangerzone machines, via `PodmanCommand.machine.list`
   * Perform raw Podman commands, via `PodmanCommand.run(args)`
4. This module should use the `podman` binary under `share/vendor/podman/`, with
   its path obtained dynamically using
   `dangerzone.util.get_resource_path("share/vendor/podman")`.
5. When an error occurs, it should raise it, and use logger.error to explain it.

## Phase 2: CLI integration in `dev_scripts`

1. Create a `dev_scripts/dangerzone-machine.py` module, in the same vein as
   `dev_scripts/dangerzone-image`.
2. Expose the above lifecycle management function as separate CLI subcommands.
   E.g., `dev_scripts/dangerzone-machine.py list`
3. Show errors by printing to stderr, potentially with red color. Allow users to
   set `--log-level` as a basic Podman option.
4. Prompt users before doing destructive actions, and allow a `--force / -f`
   flag to override these prompts.

## Phase 3: Add a bottom bar in Dangerzone

1. Add a thin bottom bar in the Dangerzone GUI that blends with the rest of the
   system. Its height should be as much as a line of text, and when empty, it
   should not be distinguished from the rest of the GUI.
2. Add the following elements in the bottom bar, from right to left:
   * An info icon that can be used later on to open a popup window with the logs
     of the background task (see eighth phase). That icon can be a Unicode emoji
     for now.
   * A message that shows 30 characters max. If longer, it should be truncated
     with ellipses, and hovering on it should show the full message.
   * A spinner icon that shows that work is underway.
3. The **text color** of the message should change colors depending on the status of
   the background task:
   * Orange: The background task is still running (show spinner and info icon)
   * Green: The background task has completed successfully (do not show spinner
     or info icon)
   * Red: The background task has failed (show only info icon)
4. The widgets should always be pushed to the right. For instance, if the info
   icon or the spinner does not exist, the text should go to the right.

## Phase 4: Create background task and move existing logic in there

1. Create a `BackgroundTask` class using `QThread` that spawns when the GUI
   application starts.
2. The `BackgroundTask` will *invoke* the logic that checks for container and
   application updates. This logic is currently spawned by
   `dangerzone/gui/updater.py`, class `UpdaterThread(QtCore.QThread)`.
   * Separate the job that checks for application updates from the job that
     checks for container updates.
3. The `BackgroundTask` will *invoke* the logic that installs the container
   image, after the update checks. This logic is currently spawned by
   `dangerzone/gui/main_window.py`, class
   `InstallContainerThread(QtCore.QThread)`.
4. Do not spawn the `UpdaterThread` / `InstallContainerThread` anymore, since
   the `BackgroundTask` is now responsible for orchestrating these actions.
5. Convert `UpdaterThread` and `InstallContainerThread` to regular classes (or
   refactor their relevant logic into standalone functions/utility classes)
   that can be called by the `BackgroundTask`.
6. Move the signals (`app_update_available`, `container_update_available`,
   `install_container_progress`, `install_container_finished`) to the
   `BackgroundTask` class.

## Phase 5: Make background task update the bottom bar

1. When the background task performs a specific job, show a message in the
   bottom bar we created in phase 3 for it:
   * Starting (when there's no action yet)
   * Checking for updates (before we start checking for updates)
   * Installing container image (if the installation strategy is not
     `DO_NOTHING`)
2. If the background task is running, add a spinner, an info icon, and make the
   text color orange.
3. If the background task has completed successfully, show a green message that
   reads "Ready".
4. If the background task has failed, show the last message in red color, and an
   info icon.
5. Communicate these status changes via signals (`status_report`). The object passed via these
   signals should be similar to ReleaseReport, and should have two message
   types:
   * ProgressReport(message: str) -> the background task is still working
   * CompletionReport(message: str, success: bool) -> the background task has
     completed, either successfully, or with a failure.

## Phase 6: Make conversions block until background task has completed successfully

1. When Dangerzone starts, let the GUI immediately show the `DocSelectionWidget`
   with the "Select suspicious documents ... " button. At the same time, the
   background task should have started and update the bottom bar.
2. Allow the users to select documents while background task is running, and
   click on "Convert to Safe Document" normally.
3. Show the conversions as blocked in the GUI, while the background task is
   running, by keeping the progress bar at 0% and not moving.
4. Start the conversions once the background task has finished successfully.

## Phase 7: Control the lifecyle of Podman machines

1. Once the background task starts, before all the other jobs running it (check
   for updates, install container image), perform the following if the platform
   is Windows or macOS:
   * Initialize a Podman machine, or check that it exists.
   * Remove stale machines, if they exist.
   * Start a Podman machine, as explained in Phase 1.
2. Once the user wants to exit the program, use `closeEvent` in
   `dangerzone.gui.main_window` to detect if a Podman machine is running, and
   stop it, before quitting.
3. If the Podman machine does not quit, and we are asked to quit a second time,
   increment a counter. If the counter exceeds a certain threshold, inform the
   user that there is a VM running in the background, and terminate.

## Phase 8: Consult logs of background task

1. Create a popup window that contains a `TracebackWidget`, that should be
   closed by default.
2. Whenever a user clicks on the info icon in the bottom bar, it should open
   once.
3. In the background task, find any `PodmanCommand.machine` command, or
   `subprocess` invocation, and pass them a pipe for stdout and stderr.
4. Spawn a thread that reads from stdout/stderr and updates the text field with
   every new line. See how the existing `TracebackWidget.process_output` is
   called.

## Phase 9: Robustness and User Experience

1. Advanced Error Handling:
   * Refine error handling for all Podman interactions, providing clear, actionable error messages.
   * Do not implement retry mechanisms for now.
2. Resource Configuration:
   * Ensure the specified machine configurations (RAM, CPUs, timezone) are correctly applied via `cpus=`, `memory=`, `timezone=` arguments to `PodmanCommand.machine.init()`.
   * Consider making these configurable by the user.
3. Cross-Platform Compatibility:
   * Thoroughly test on Linux, Windows, and macOS to identify and address platform-specific issues.
4. Comprehensive Testing:
   * Write automated unit tests for `dangerzone/podman_machine.py`.
   * Write integration tests that simulate the full lifecycle of Dangerzone, including machine creation and cleanup.

## Phase 10: Documentation and Release

1. Update Documentation:
   * Update the `README.md`, `INSTALL.md`, and any developer documentation with details on the new Podman machine management.
   * Document the `dangerzone-machine` command.
2. Release Notes: Prepare release notes highlighting this new feature.
