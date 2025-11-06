//! Example demonstrating the full Rust wrapper workflow.
//!
//! This example shows how to:
//! 1. Create a mock pixel stream
//! 2. Read pixel data using PixelStreamReader
//! 3. Reconstruct a PDF using PdfReconstructor
//!
//! Run with: cargo run --example full_workflow

use dangerzone_rust::{PdfReconstructor, PixelStreamReader};
use std::fs::File;
use std::io::{Cursor, Write};

fn create_mock_stream() -> Vec<u8> {
    let mut data = Vec::new();
    
    // Write page count (2 pages)
    data.extend_from_slice(&2u16.to_be_bytes());
    
    // Page 1: 100x100 red pixels
    let width1 = 100u16;
    let height1 = 100u16;
    data.extend_from_slice(&width1.to_be_bytes());
    data.extend_from_slice(&height1.to_be_bytes());
    for _ in 0..(width1 * height1) {
        data.extend_from_slice(&[255, 0, 0]); // Red
    }
    
    // Page 2: 150x100 blue pixels
    let width2 = 150u16;
    let height2 = 100u16;
    data.extend_from_slice(&width2.to_be_bytes());
    data.extend_from_slice(&height2.to_be_bytes());
    for _ in 0..(width2 * height2) {
        data.extend_from_slice(&[0, 0, 255]); // Blue
    }
    
    data
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("Dangerzone Rust Wrapper - Full Workflow Example");
    println!("================================================\n");
    
    // Step 1: Create a mock pixel stream
    println!("Step 1: Creating mock pixel stream...");
    let stream = create_mock_stream();
    println!("  Created {} bytes of stream data\n", stream.len());
    
    // Step 2: Read pixel data from the stream
    println!("Step 2: Reading pixel data from stream...");
    let mut reader = PixelStreamReader::new(Cursor::new(stream));
    let pages = reader.read_all_pages()?;
    println!("  Successfully read {} pages:", pages.len());
    for (i, page) in pages.iter().enumerate() {
        println!(
            "    Page {}: {}x{} pixels ({} bytes)",
            i + 1,
            page.width,
            page.height,
            page.pixels.len()
        );
    }
    println!();
    
    // Step 3: Reconstruct PDF from pixels
    println!("Step 3: Reconstructing PDF from pixels...");
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages)?;
    println!("  Generated PDF: {} bytes\n", pdf_data.len());
    
    // Step 4: Save the PDF
    let output_path = "/tmp/example-output.pdf";
    println!("Step 4: Saving PDF to {}...", output_path);
    let mut file = File::create(output_path)?;
    file.write_all(&pdf_data)?;
    println!("  PDF saved successfully!\n");
    
    println!("✓ Workflow completed successfully!");
    println!("\nYou can view the generated PDF at: {}", output_path);
    
    Ok(())
}
