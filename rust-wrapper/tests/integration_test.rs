//! Integration tests for the full PDF reconstruction workflow.

use dangerzone_rust::{PdfReconstructor, PixelStreamReader};
use std::io::Cursor;

/// Helper function to create a test pixel stream.
fn create_test_stream(pages: Vec<(u16, u16, Vec<u8>)>) -> Vec<u8> {
    let mut data = Vec::new();
    
    // Write page count
    let page_count = pages.len() as u16;
    data.extend_from_slice(&page_count.to_be_bytes());
    
    // Write each page
    for (width, height, pixels) in pages {
        data.extend_from_slice(&width.to_be_bytes());
        data.extend_from_slice(&height.to_be_bytes());
        data.extend_from_slice(&pixels);
    }
    
    data
}

#[test]
fn test_full_workflow_single_page() {
    // Create a simple test page (10x10 red image)
    let width = 10u16;
    let height = 10u16;
    let mut pixels = Vec::new();
    for _ in 0..(width * height) {
        pixels.extend_from_slice(&[255, 0, 0]);
    }
    
    // Create the stream
    let stream = create_test_stream(vec![(width, height, pixels)]);
    
    // Read the stream
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages().expect("Failed to read pages");
    
    assert_eq!(pages.len(), 1);
    assert_eq!(pages[0].width, width);
    assert_eq!(pages[0].height, height);
    
    // Reconstruct PDF
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages).expect("Failed to reconstruct PDF");
    
    // Verify PDF is valid
    assert!(pdf_data.starts_with(b"%PDF-"));
    assert!(pdf_data.len() > 100);
}

#[test]
fn test_full_workflow_multiple_pages() {
    // Create multiple test pages with different sizes
    let mut red_pixels = Vec::new();
    for _ in 0..25 { red_pixels.extend_from_slice(&[255, 0, 0]); }
    
    let mut green_pixels = Vec::new();
    for _ in 0..80 { green_pixels.extend_from_slice(&[0, 255, 0]); }
    
    let mut blue_pixels = Vec::new();
    for _ in 0..80 { blue_pixels.extend_from_slice(&[0, 0, 255]); }
    
    let pages_data = vec![
        (5u16, 5u16, red_pixels),      // Red 5x5
        (10u16, 8u16, green_pixels),   // Green 10x8
        (8u16, 10u16, blue_pixels),    // Blue 8x10
    ];
    
    // Create the stream
    let stream = create_test_stream(pages_data.clone());
    
    // Read the stream
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages().expect("Failed to read pages");
    
    assert_eq!(pages.len(), 3);
    for (i, page) in pages.iter().enumerate() {
        assert_eq!(page.width, pages_data[i].0);
        assert_eq!(page.height, pages_data[i].1);
    }
    
    // Reconstruct PDF
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages).expect("Failed to reconstruct PDF");
    
    // Verify PDF is valid
    assert!(pdf_data.starts_with(b"%PDF-"));
    // Multi-page PDFs should be larger
    assert!(pdf_data.len() > 200);
}

#[test]
fn test_workflow_with_custom_dpi() {
    // Create a test page
    let width = 150u16;
    let height = 150u16;
    let mut pixels = Vec::new();
    for _ in 0..(width * height) {
        pixels.extend_from_slice(&[128, 128, 128]); // Gray
    }
    
    let stream = create_test_stream(vec![(width, height, pixels)]);
    
    // Read the stream
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages().expect("Failed to read pages");
    
    // Reconstruct PDF with custom DPI
    let reconstructor = PdfReconstructor::with_dpi(300.0);
    let pdf_data = reconstructor.reconstruct(pages).expect("Failed to reconstruct PDF");
    
    // Verify PDF is valid
    assert!(pdf_data.starts_with(b"%PDF-"));
}

#[test]
fn test_workflow_different_color_patterns() {
    // Create pages with different color patterns to ensure RGB handling is correct
    let mut red_page = Vec::new();
    let mut green_page = Vec::new();
    let mut blue_page = Vec::new();
    let mut white_page = Vec::new();
    let mut black_page = Vec::new();
    
    for _ in 0..100 {
        red_page.extend_from_slice(&[255, 0, 0]);
        green_page.extend_from_slice(&[0, 255, 0]);
        blue_page.extend_from_slice(&[0, 0, 255]);
        white_page.extend_from_slice(&[255, 255, 255]);
        black_page.extend_from_slice(&[0, 0, 0]);
    }
    
    let pages_data = vec![
        (10u16, 10u16, red_page),
        (10u16, 10u16, green_page),
        (10u16, 10u16, blue_page),
        (10u16, 10u16, white_page),
        (10u16, 10u16, black_page),
    ];
    
    let stream = create_test_stream(pages_data);
    
    // Read and reconstruct
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages().expect("Failed to read pages");
    
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages).expect("Failed to reconstruct PDF");
    
    // Verify PDF is valid
    assert!(pdf_data.starts_with(b"%PDF-"));
    assert_eq!(reader.read_all_pages().unwrap_err().to_string(), "IO error: failed to fill whole buffer");
}

#[test]
fn test_workflow_error_handling() {
    // Test with invalid stream (not enough data)
    let invalid_stream = vec![0x00, 0x01]; // Says 1 page but no page data
    let mut reader = PixelStreamReader::new(Cursor::new(invalid_stream));
    
    let result = reader.read_all_pages();
    assert!(result.is_err());
}

#[test]
fn test_workflow_large_page() {
    // Create a larger page to test efficiency
    let width = 100u16;
    let height = 100u16;
    let mut pixels = Vec::new();
    for _ in 0..(width * height) {
        pixels.extend_from_slice(&[200, 100, 50]); // Orange-ish
    }
    
    let stream = create_test_stream(vec![(width, height, pixels)]);
    
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages().expect("Failed to read pages");
    
    assert_eq!(pages.len(), 1);
    assert_eq!(pages[0].pixels.len(), 30000); // 100*100*3
    
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages).expect("Failed to reconstruct PDF");
    
    assert!(pdf_data.starts_with(b"%PDF-"));
}
