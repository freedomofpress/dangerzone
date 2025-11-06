# Dangerzone Rust Wrapper

A thin Rust wrapper for running containers, passing data, and reconstructing PDFs from streamed pixel data.

## Overview

This library provides three main components:

1. **Container Runner** - Execute containers and pass data to them
2. **Stream Reader** - Parse pixel data stream from container output
3. **PDF Reconstructor** - Rebuild PDF documents from pixel data

## Data Format

The pixel stream format from container stdout:
- Page count (2 bytes, big-endian int)
- For each page:
  - Page width (2 bytes, big-endian int)
  - Page height (2 bytes, big-endian int)
  - Page data (width × height × 3 bytes, RGB pixels)

## Usage Example

```rust
use dangerzone_rust::{ContainerRunner, PixelStreamReader, PdfReconstructor};
use std::fs::File;
use std::io::Write;

// Run a container to convert a document to pixels
let runner = ContainerRunner::new("dangerzone-conversion".to_string());
let mut child = runner.run(
    "dangerzone-image",
    &["/usr/bin/python3", "-m", "dangerzone.conversion.doc_to_pixels"],
    &[],
)?;

// Read pixel data from container stdout
let stdout = child.stdout.take().unwrap();
let mut stream_reader = PixelStreamReader::new(stdout);
let pages = stream_reader.read_all_pages()?;

// Reconstruct PDF from pixels
let reconstructor = PdfReconstructor::new();
let pdf_data = reconstructor.reconstruct(pages)?;

// Save the PDF
let mut output = File::create("safe.pdf")?;
output.write_all(&pdf_data)?;
```

## Testing

Run the test suite:

```bash
cargo test
```

Run all tests including integration tests that require a container runtime:

```bash
cargo test -- --ignored
```

## Features

- **Stream parsing**: Efficiently reads and validates pixel data stream
- **Error handling**: Comprehensive error types for all operations
- **PDF reconstruction**: Creates valid PDF documents from RGB pixel data
- **Container runtime detection**: Automatically detects podman or docker
- **DPI support**: Configurable DPI for accurate PDF dimensions
- **Comprehensive tests**: Unit tests for all components

## License

This library is part of Dangerzone and is licensed under the AGPL-3.0 license.
