//! Dangerzone Rust CLI
//!
//! A command-line interface for converting potentially dangerous documents to safe PDFs.
//! This binary mimics the functionality of dangerzone-cli, using the Rust wrapper
//! to run containers, parse pixel streams, and reconstruct PDFs.

use clap::Parser;
use dangerzone_rust::{ContainerRunner, PdfReconstructor, PixelStreamReader};
use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};

/// Dangerzone - Convert potentially dangerous documents to safe PDFs
#[derive(Parser, Debug)]
#[command(name = "dangerzone-rust")]
#[command(version, about, long_about = None)]
struct Args {
    /// Input file(s) to convert
    #[arg(required = true)]
    filenames: Vec<PathBuf>,

    /// Output filename (only valid with single input file)
    #[arg(short, long)]
    output_filename: Option<PathBuf>,

    /// Enable debug mode
    #[arg(short, long)]
    debug: bool,

    /// Container image to use
    #[arg(long, default_value = "localhost/dangerzone.rocks/dangerzone")]
    container_image: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Display banner
    display_banner();

    // Validate arguments
    if args.filenames.len() > 1 && args.output_filename.is_some() {
        eprintln!("Error: --output-filename can only be used with one input file.");
        std::process::exit(1);
    }

    // Process each file
    let mut success_count = 0;
    let mut failed_files = Vec::new();

    for input_path in &args.filenames {
        if !input_path.exists() {
            eprintln!("Error: File not found: {}", input_path.display());
            failed_files.push(input_path.clone());
            continue;
        }

        let output_path = if let Some(ref output) = args.output_filename {
            output.clone()
        } else {
            generate_output_filename(input_path)
        };

        println!("\nConverting: {}", input_path.display());
        println!("Output: {}", output_path.display());

        match convert_document(input_path, &output_path, &args.container_image, args.debug) {
            Ok(_) => {
                println!("✓ Successfully converted to safe PDF");
                success_count += 1;
            }
            Err(e) => {
                eprintln!("✗ Conversion failed: {}", e);
                failed_files.push(input_path.clone());
            }
        }
    }

    // Summary
    println!();
    println!("{}", "=".repeat(50));
    println!("Conversion Summary:");
    println!("  Successful: {}", success_count);
    println!("  Failed: {}", failed_files.len());

    if !failed_files.is_empty() {
        println!("\nFailed files:");
        for file in &failed_files {
            println!("  - {}", file.display());
        }
        std::process::exit(1);
    }

    Ok(())
}

fn convert_document(
    input_path: &Path,
    output_path: &Path,
    container_image: &str,
    debug: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    // Read input file
    let input_data = std::fs::read(input_path)?;

    // Create container runner
    let container_name = format!(
        "dangerzone-rust-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_millis()
    );

    let runner = ContainerRunner::with_auto_runtime(container_name)?;

    // Run container with document conversion command
    let command = &[
        "/usr/bin/python3",
        "-m",
        "dangerzone.conversion.doc_to_pixels",
    ];
    let extra_args = if debug {
        vec!["-e", "RUNSC_DEBUG=1"]
    } else {
        vec![]
    };

    let mut child = runner.run_with_input(container_image, command, &extra_args, &input_data)?;

    // Read pixel stream from container stdout
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let mut stream_reader = PixelStreamReader::new(stdout);
    let pages = stream_reader.read_all_pages()?;

    // Wait for container to finish
    let status = child.wait()?;
    if !status.success() {
        return Err(format!("Container exited with status: {}", status).into());
    }

    // Reconstruct PDF from pixels
    let reconstructor = PdfReconstructor::new();
    let pdf_data = reconstructor.reconstruct(pages)?;

    // Write output PDF
    let mut output_file = File::create(output_path)?;
    output_file.write_all(&pdf_data)?;

    Ok(())
}

fn generate_output_filename(input_path: &Path) -> PathBuf {
    let mut output = input_path.to_path_buf();

    // Get the file stem (name without extension)
    let stem = input_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("output");

    // Create safe filename
    output.set_file_name(format!("{}-safe.pdf", stem));

    output
}

fn display_banner() {
    println!("╭──────────────────────────╮");
    println!("│           ▄██▄           │");
    println!("│          ██████          │");
    println!("│         ███▀▀▀██         │");
    println!("│        ███   ████        │");
    println!("│       ███   ██████       │");
    println!("│      ███   ▀▀▀▀████      │");
    println!("│     ███████  ▄██████     │");
    println!("│    ███████ ▄█████████    │");
    println!("│   ████████████████████   │");
    println!("│    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    │");
    println!("│                          │");
    println!("│    Dangerzone (Rust)     │");
    println!("│ https://dangerzone.rocks │");
    println!("╰──────────────────────────╯");
}
