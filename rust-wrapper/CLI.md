# CLI Binary Documentation

## Overview

The `dangerzone-rust` binary is a command-line interface that mimics the functionality of `dangerzone-cli`, providing a Rust-based alternative for converting potentially dangerous documents to safe PDFs.

## Features

- **Multiple file conversion**: Process multiple documents in a single command
- **Custom output naming**: Specify output filename for single file conversions
- **Debug mode**: Enable detailed logging for troubleshooting
- **Container runtime detection**: Automatically detects and uses Podman or Docker
- **Progress reporting**: Clear feedback on conversion status and results
- **Error handling**: Comprehensive error messages for common issues

## Installation

### Building from source

```bash
cd rust-wrapper
cargo build --release --bin dangerzone-rust
```

The binary will be available at `target/release/dangerzone-rust`.

### Using pre-built binaries

Pre-built binaries are available as CI artifacts from the GitHub Actions workflow.

## Usage

### Basic conversion

Convert a single document:
```bash
dangerzone-rust document.pdf
```

This creates `document-safe.pdf` in the same directory.

### Multiple files

Convert multiple documents at once:
```bash
dangerzone-rust file1.pdf file2.docx file3.png
```

Each file will be converted to a corresponding `-safe.pdf` file.

### Custom output filename

Specify a custom output filename (single file only):
```bash
dangerzone-rust input.pdf --output-filename my-safe-document.pdf
```

### Debug mode

Enable debug mode for detailed logging:
```bash
dangerzone-rust document.pdf --debug
```

### Custom container image

Use a specific container image:
```bash
dangerzone-rust document.pdf --container-image my-custom-image:latest
```

## Command-line Options

```
Usage: dangerzone-rust [OPTIONS] <FILENAMES>...

Arguments:
  <FILENAMES>...  Input file(s) to convert

Options:
  -o, --output-filename <OUTPUT_FILENAME>
          Output filename (only valid with single input file)
  
  -d, --debug
          Enable debug mode
  
  --container-image <CONTAINER_IMAGE>
          Container image to use
          [default: localhost/dangerzone.rocks/dangerzone]
  
  -h, --help
          Print help
  
  -V, --version
          Print version
```

## Requirements

### Container Runtime

The binary requires either Podman or Docker to be installed and running. The binary automatically detects which runtime is available.

### Container Image

The Dangerzone container image must be available:
```bash
# Default image location
localhost/dangerzone.rocks/dangerzone
```

To use the binary with a different image, use the `--container-image` option.

## Exit Codes

- `0`: All conversions successful
- `1`: One or more conversions failed

## Examples

### Example 1: Convert a PDF with default settings

```bash
$ dangerzone-rust suspicious.pdf

╭──────────────────────────╮
│           ▄██▄           │
│          ██████          │
│         ███▀▀▀██         │
│        ███   ████        │
│       ███   ██████       │
│      ███   ▀▀▀▀████      │
│     ███████  ▄██████     │
│    ███████ ▄█████████    │
│   ████████████████████   │
│    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    │
│                          │
│    Dangerzone (Rust)     │
│ https://dangerzone.rocks │
╰──────────────────────────╯

Converting: suspicious.pdf
Output: suspicious-safe.pdf
✓ Successfully converted to safe PDF

==================================================
Conversion Summary:
  Successful: 1
  Failed: 0
```

### Example 2: Convert multiple files

```bash
$ dangerzone-rust report.pdf presentation.pptx photo.jpg

Converting: report.pdf
Output: report-safe.pdf
✓ Successfully converted to safe PDF

Converting: presentation.pptx
Output: presentation-safe.pdf
✓ Successfully converted to safe PDF

Converting: photo.jpg
Output: photo-safe.pdf
✓ Successfully converted to safe PDF

==================================================
Conversion Summary:
  Successful: 3
  Failed: 0
```

### Example 3: Handle errors

```bash
$ dangerzone-rust missing.pdf existing.pdf

Error: File not found: missing.pdf

Converting: existing.pdf
Output: existing-safe.pdf
✓ Successfully converted to safe PDF

==================================================
Conversion Summary:
  Successful: 1
  Failed: 1

Failed files:
  - missing.pdf
```

## Testing

### Run CLI tests

```bash
cd rust-wrapper
cargo test --test cli_test
```

### Run integration test script

```bash
cd rust-wrapper
./test_cli.sh
```

## Troubleshooting

### Binary not found

Ensure you've built the binary:
```bash
cargo build --bin dangerzone-rust
```

### Container runtime not found

Install Podman or Docker:
- **Podman**: https://podman.io/getting-started/installation
- **Docker**: https://docs.docker.com/get-docker/

### Container image not found

Ensure the Dangerzone container image is available locally, or specify a custom image with `--container-image`.

## Comparison with Python CLI

The Rust binary provides similar functionality to `dangerzone-cli` with these differences:

**Similarities:**
- Convert documents to safe PDFs
- Multiple file support
- Debug mode
- Banner display

**Differences:**
- Written in Rust (vs Python)
- Simplified argument handling
- No OCR support yet (future enhancement)
- Direct container interaction (no Python dependencies)

## Performance

The Rust binary offers comparable performance to the Python CLI, with the actual conversion time dominated by the container execution rather than the wrapper overhead.

## Future Enhancements

Potential improvements:
- OCR language support
- Archive original files option
- Parallel processing of multiple files
- Progress bars for long conversions
- Configuration file support
