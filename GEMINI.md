This repository contains the source code for Dangerzone, a tool that converts
potentially dangerous documents (like PDFs, Office documents, or images) into
safe PDFs.

It works by sandboxing the original document, converting it to raw pixel data,
and then creating a new PDF from that data outside the sandbox. This process
eliminates any potential threats embedded in the
original file.

## Relevant Files

 * pyproject.toml: Defines the project's Python dependencies and metadata.
 * dodo.py: Contains the build automation tasks for the project, using the doit library.
 * Makefile: Contains a set of commands for common development tasks, like linting, testing, and building.
 * README.md: Provides a general overview of the project, including installation instructions and features.
 * dangerzone/: The main source code for the Dangerzone application.
 * tests/: Contains the test suite for the project.
 * .github/workflows/: Contains the CI/CD workflows for the project.

## Commands

### General

 * make help: Show all the available make commands.
 * make lint: Check the code for linting, formatting, and typing issues.
 * make fix: Automatically fix linting and formatting issues.
 * make test: Run the test suite.
 * poetry install: Install project dependencies.

### Building

 * make build-macos-intel: Build the macOS Intel package.
 * make build-macos-arm: Build the macOS Apple Silicon package.
 * make build-linux: Build the Linux packages (.rpm and .deb).
 * dodo: Run all the build tasks.

## CI/CD

The CI/CD workflows are defined in the .github/workflows/ directory. The main workflows are:

 * build.yml: Builds the project for all supported platforms.
 * ci.yml: Runs the main CI pipeline, which includes linting, testing, and building.
 * check_pr.yml: Runs a set of checks on every pull request.
 * release-container-image.yml: Releases the container image to the registry.

## Code Structure

The project is a Python application with a clear separation of concerns:

 * Core Logic (`dangerzone/`): This is the main Python package.
     * cli.py and gui/: Separate modules for the command-line interface and the graphical user interface, respectively. This indicates that UI logic is decoupled from the core functionality.
     * conversion/: Handles the document conversion process **within** the sandbox, which is the central feature of the application.
     * isolation_provider/: Manages the sandboxing environments (like Podman, Docker, or Qubes), a critical part of the security model.
     * settings.py: Manages application configuration.
 * Testing (`tests/`): The test suite is located in the tests directory and appears to mirror the structure of the dangerzone package. It uses pytest for testing.
 * Build and Automation (`dodo.py`, `Makefile`, `dev_scripts/`):
     * dodo.py acts as the primary build script, defining a series of tasks for creating release artifacts for different operating systems.
     * Makefile provides a set of developer-friendly shortcuts for common tasks like linting (make lint), testing (make test), and applying automatic fixes (make fix).
     * dev_scripts/ contains helper scripts that are likely invoked by the build and automation tools.
 * Dependencies (`pyproject.toml`): The project uses poetry for dependency management. Dependencies are split into logical groups: core, packaging, linting, and testing.
 * Installation (`install/`): Contains platform-specific scripts and templates for creating installers for macOS, Linux, and Windows.
 * CI/CD (`.github/workflows/`): All continuous integration and deployment logic is defined in GitHub Actions workflows, automating checks, builds, and releases.

Development Guidelines

The repository enforces a consistent and high-quality code style through a combination of tools and conventions:

 * Linting and Formatting: The project uses Ruff for both linting and code formatting.
     * Run make lint to check for issues.
     * Run make fix to automatically fix any fixable issues.
     * This ensures a consistent code style and helps catch potential bugs early.
 * Static Typing: The project uses mypy for static type checking, with a strict configuration (--disallow-untyped-defs, --disallow-incomplete-defs).
     * This means that new code should be fully type-hinted to pass the checks.
 * Testing: Pytest is the standard for writing tests.
     * The Makefile provides a make test command to run the suite.
     * There's a special consideration for GUI tests, which are run in separate processes to prevent state-related failures. This is a convention that should be followed when adding new GUI tests.
 * Dependency Management: All Python dependencies must be managed using Poetry.
     * Use poetry add <package> to add a runtime dependency.
     * Use poetry add --group <group> <package> to add a development dependency to a specific group (e.g., lint, test).
 * Build Process: While dodo.py contains the detailed build logic, developers should use the simpler make commands for their daily workflow. The doit tasks are more for the CI/CD and release packaging process.
 * Platform support: All code, unless bound to a specific platform, should be
   able to run across platforms and architectures, such as Windows, Intel macOS,
   and macOS with Apple Silicon CPU. This means that paths must be defined as `Path("dir") / "name"` and
  not `Path("dir/name")`
 * Subprocess handling: Use the `subprocess_run` helper, or invoke
   `subprocess.Popen/run` with `startupinfo=get_subprocess_startupinfo()`

Python conventions

* Do not import unused modules. Sort them like `ruff` does.
