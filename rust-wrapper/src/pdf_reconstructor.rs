//! PDF reconstruction from pixel data.
//!
//! This module converts pixel data back into a PDF document.

use crate::stream_reader::PageData;
use printpdf::*;
use std::io::BufWriter;

/// DPI used for PDF reconstruction (must match DEFAULT_DPI from Python code).
const DEFAULT_DPI: f32 = 150.0;

/// Errors that can occur during PDF reconstruction.
#[derive(Debug, thiserror::Error)]
pub enum PdfError {
    #[error("No pages provided")]
    NoPages,

    #[error("PDF creation error: {0}")]
    PdfCreation(String),

    #[error("Invalid page dimensions: width={width}, height={height}")]
    InvalidDimensions { width: u16, height: u16 },

    #[error("Image creation error: {0}")]
    ImageCreation(String),
}

/// Reconstructs PDFs from pixel data.
pub struct PdfReconstructor {
    dpi: f32,
}

impl Default for PdfReconstructor {
    fn default() -> Self {
        PdfReconstructor { dpi: DEFAULT_DPI }
    }
}

impl PdfReconstructor {
    /// Creates a new PdfReconstructor with the default DPI.
    pub fn new() -> Self {
        Self::default()
    }

    /// Creates a new PdfReconstructor with a custom DPI.
    pub fn with_dpi(dpi: f32) -> Self {
        PdfReconstructor { dpi }
    }

    /// Converts pixels to PDF dimensions in points (1/72 inch).
    fn pixels_to_points(&self, pixels: u16) -> f32 {
        (pixels as f32 / self.dpi) * 72.0
    }

    /// Converts points to millimeters.
    fn points_to_mm(points: f32) -> f32 {
        points * 0.352778
    }

    /// Reconstructs a PDF from pixel data pages.
    pub fn reconstruct(&self, pages: Vec<PageData>) -> Result<Vec<u8>, PdfError> {
        if pages.is_empty() {
            return Err(PdfError::NoPages);
        }

        // Use the first page dimensions for the initial page
        let first_page = &pages[0];
        if first_page.width == 0 || first_page.height == 0 {
            return Err(PdfError::InvalidDimensions {
                width: first_page.width,
                height: first_page.height,
            });
        }

        let first_width_pt = self.pixels_to_points(first_page.width);
        let first_height_pt = self.pixels_to_points(first_page.height);

        // Create a new PDF document with the first page
        let (doc, page_idx, layer_idx) = PdfDocument::new(
            "Dangerzone Safe PDF",
            Mm(Self::points_to_mm(first_width_pt)),
            Mm(Self::points_to_mm(first_height_pt)),
            "Layer 1",
        );

        // Add the first page content
        self.add_page_image(&doc, page_idx, layer_idx, first_page)?;

        // Add remaining pages
        for page in pages.iter().skip(1) {
            if page.width == 0 || page.height == 0 {
                return Err(PdfError::InvalidDimensions {
                    width: page.width,
                    height: page.height,
                });
            }

            let width_pt = self.pixels_to_points(page.width);
            let height_pt = self.pixels_to_points(page.height);

            let (page_idx, layer_idx) = doc.add_page(
                Mm(Self::points_to_mm(width_pt)),
                Mm(Self::points_to_mm(height_pt)),
                "Layer 1",
            );

            self.add_page_image(&doc, page_idx, layer_idx, page)?;
        }

        // Save the PDF to a buffer
        let mut buf = Vec::new();
        doc.save(&mut BufWriter::new(&mut buf))
            .map_err(|e| PdfError::PdfCreation(e.to_string()))?;

        Ok(buf)
    }

    /// Adds an image to a PDF page.
    fn add_page_image(
        &self,
        doc: &PdfDocumentReference,
        page_idx: PdfPageIndex,
        layer_idx: PdfLayerIndex,
        page: &PageData,
    ) -> Result<(), PdfError> {
        // Create image from raw RGB data
        let image = Image::from_dynamic_image(&self.create_rgb_image(page)?);

        // Get the current layer
        let current_layer = doc.get_page(page_idx).get_layer(layer_idx);

        // Calculate dimensions in mm
        let width_pt = self.pixels_to_points(page.width);
        let height_pt = self.pixels_to_points(page.height);
        let width_mm = Self::points_to_mm(width_pt);
        let height_mm = Self::points_to_mm(height_pt);

        // Add the image to fill the entire page
        image.add_to_layer(
            current_layer,
            ImageTransform {
                translate_x: Some(Mm(0.0)),
                translate_y: Some(Mm(0.0)),
                scale_x: Some(width_mm),
                scale_y: Some(height_mm),
                ..Default::default()
            },
        );

        Ok(())
    }

    /// Creates a DynamicImage from RGB pixel data using the image crate.
    fn create_rgb_image(&self, page: &PageData) -> Result<::image::DynamicImage, PdfError> {
        let img = ::image::ImageBuffer::<::image::Rgb<u8>, _>::from_raw(
            page.width as u32,
            page.height as u32,
            page.pixels.clone(),
        )
        .ok_or(PdfError::InvalidDimensions {
            width: page.width,
            height: page.height,
        })?;

        Ok(::image::DynamicImage::ImageRgb8(img))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stream_reader::PageData;

    #[test]
    fn test_new_reconstructor() {
        let reconstructor = PdfReconstructor::new();
        assert_eq!(reconstructor.dpi, DEFAULT_DPI);
    }

    #[test]
    fn test_custom_dpi() {
        let reconstructor = PdfReconstructor::with_dpi(300.0);
        assert_eq!(reconstructor.dpi, 300.0);
    }

    #[test]
    fn test_pixels_to_points() {
        let reconstructor = PdfReconstructor::new();
        // 150 pixels at 150 DPI = 1 inch = 72 points
        assert_eq!(reconstructor.pixels_to_points(150), 72.0);
    }

    #[test]
    fn test_points_to_mm() {
        // 72 points = 1 inch = 25.4 mm
        let mm = PdfReconstructor::points_to_mm(72.0);
        assert!((mm - 25.4).abs() < 0.1);
    }

    #[test]
    fn test_reconstruct_empty_pages() {
        let reconstructor = PdfReconstructor::new();
        let result = reconstructor.reconstruct(vec![]);
        assert!(matches!(result, Err(PdfError::NoPages)));
    }

    #[test]
    fn test_reconstruct_single_page() {
        let reconstructor = PdfReconstructor::new();

        // Create a simple 2x2 red page
        let pixels = vec![
            255, 0, 0, // red
            255, 0, 0, // red
            255, 0, 0, // red
            255, 0, 0, // red
        ];
        let page = PageData::new(2, 2, pixels).unwrap();

        let result = reconstructor.reconstruct(vec![page]);
        assert!(result.is_ok());

        let pdf_data = result.unwrap();
        // PDF should start with PDF header
        assert!(pdf_data.starts_with(b"%PDF-"));
    }

    #[test]
    fn test_reconstruct_multiple_pages() {
        let reconstructor = PdfReconstructor::new();

        // Create two simple pages
        let page1 = PageData::new(2, 2, vec![255u8; 12]).unwrap();
        let page2 = PageData::new(3, 3, vec![0u8; 27]).unwrap();

        let result = reconstructor.reconstruct(vec![page1, page2]);
        assert!(result.is_ok());

        let pdf_data = result.unwrap();
        assert!(pdf_data.starts_with(b"%PDF-"));
        // PDF should be larger with multiple pages
        assert!(pdf_data.len() > 100);
    }

    #[test]
    fn test_reconstruct_invalid_dimensions() {
        let reconstructor = PdfReconstructor::new();

        // Create a page with zero dimensions
        let page = PageData {
            width: 0,
            height: 100,
            pixels: vec![],
        };

        let result = reconstructor.reconstruct(vec![page]);
        assert!(matches!(
            result,
            Err(PdfError::InvalidDimensions {
                width: 0,
                height: 100
            })
        ));
    }
}
