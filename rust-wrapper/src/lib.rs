//! Dangerzone Rust Wrapper
//!
//! This library provides a thin wrapper for running containers, passing data,
//! and reconstructing PDFs from streamed pixel data.

pub mod container;
pub mod pdf_reconstructor;
pub mod stream_reader;

pub use container::{ContainerError, ContainerRunner};
pub use pdf_reconstructor::{PdfError, PdfReconstructor};
pub use stream_reader::{PixelStreamReader, StreamError};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_library_exports() {
        // This test ensures that the main types are properly exported
        let _: fn() -> Result<ContainerRunner, ContainerError> =
            || Ok(ContainerRunner::new("test-container".to_string()));
    }
}
