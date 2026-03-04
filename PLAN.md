# Objective
Update Dangerzone to support converting archives by extracting them in the container and converting each file individually. This involves refactoring the conversion script to accept commands and arguments, and updating the client to manage a persistent container for multi-step conversion using nested `exec` calls.

# Key Files & Context
- `dangerzone/conversion/doc_to_pixels.py`: The conversion script running inside the container. Will be updated to handle `index` and `sanitize` commands.
- `dangerzone/isolation_provider/container.py`: Manages the Podman/Docker container. Will be updated to start a persistent container and issue `exec` commands that bridge into the gVisor sandbox.
- `dangerzone/isolation_provider/base.py`: Base class for isolation providers. `convert` method will be updated to handle the new multi-file workflow.
- `container_helpers/entrypoint.py`: Entrypoint for the container. It starts `runsc` with a hardcoded container ID `dangerzone`.

# Implementation Steps

## 1. Container-side: Refactor `doc_to_pixels.py`
- [x] **`index` command**:
    - [x] Accept an optional `--output-dir` (default: `/tmp/dz-extracted-<random_hex>`).
    - [x] Read stdin and save to a temporary location.
    - [x] If it's an archive (ZIP, TAR, etc.):
        - [x] Recursively extract all contents to `output_dir`.
        - [x] Return the list of absolute paths for all extracted files.
    - [x] If it's a single file:
        - [x] Move the file to `output_dir`.
        - [x] Return the path `output_dir` itself (without a trailing slash).
    - [x] **Protocol**: `<num files>: uint16`, then for each file: `<length>: uint16`, `<path>: varchar`.
- [x] **`sanitize` command**:
    - [x] Accept a mandatory absolute path argument.
    - [x] Perform the conversion (doc to pixels) on the file at that path.
    - [x] Maintain existing behavior: pixels to stdout, progress/errors to stderr.
- [x] **Backwards Compatibility**: Maintain the original behavior (no arguments) to read from stdin and convert to pixels if no command is provided.

## 2. Client-side: Refactor `Container` and `IsolationProvider`
- [x] **Persistent Container**:
    - [x] In `Container.start_doc_to_pixels_proc`, change the command to `["sleep", "infinity"]`. This ensures the gVisor sandbox stays alive.
- [x] **Nested Exec**:
    - [x] Implement a `run_exec` method in the `Container` provider.
    - [x] This method will run: `podman exec <container_name> /usr/bin/runsc --root=/home/dangerzone/.containers exec dangerzone <command>`.
- [x] **`IsolationProvider.convert` workflow**:
    1. [x] Start the persistent container.
    2. [x] Issue the `index` command via `run_exec`, passing the document data to stdin.
    3. [x] Read the returned file list (paths).
    4. [x] For each path:
        - [x] Issue the `sanitize <path>` command via `run_exec`.
        - [x] Read pixel data from stdout and construct PDF pages.
        - [x] Update progress: `(file_index + (page_index / n_pages)) / num_files`.
    5. [x] Save the final aggregated PDF.

## 3. GUI Update
- [x] Update `get_supported_extensions` in `main_window.py` to include archive extensions (`.zip`, `.tar`, `.gz`, `.bz2`, `.7z`, `.xz`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`) on non-Qubes platforms.
- [x] Fix inverted HWP filter logic in `main_window.py`.

## 4. Filename Sanitization & Security
- Ensure the client-side distrusts the paths returned by `index` and sanitizes them for use in progress reporting and internal mapping.
- Verify that `podman exec` and `runsc exec` correctly handle stdin/stdout for streaming data.

## 5. Error Handling
- Capture and map exit codes from `runsc exec` back to `ConversionException`.
- Ensure the persistent container is correctly cleaned up (killed) after conversion or on failure.

# Verification & Testing
- Unit tests for recursive extraction and path reporting in `doc_to_pixels.py`.
- Integration tests with:
    - Single PDF files.
    - ZIP archives with nested archives and various file types.
    - Empty or corrupted archives.
- Verify progress bar accuracy during multi-file conversion.
