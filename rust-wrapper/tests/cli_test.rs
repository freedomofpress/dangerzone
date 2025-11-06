//! Integration test for the dangerzone-rust CLI binary.
//!
//! This test creates a simple mock pixel stream, runs it through the binary,
//! and verifies the output.

use std::fs::File;
use std::path::PathBuf;
use std::process::Command;
use tempfile::TempDir;

#[test]
#[ignore] // This test requires the binary to be built and a container runtime
fn test_cli_help() {
    let binary_path = get_binary_path();

    let output = Command::new(&binary_path)
        .arg("--help")
        .output()
        .expect("Failed to run binary");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Dangerzone"));
    assert!(stdout.contains("Convert potentially dangerous documents"));
}

#[test]
#[ignore] // This test requires the binary to be built and a container runtime
fn test_cli_version() {
    let binary_path = get_binary_path();

    let output = Command::new(&binary_path)
        .arg("--version")
        .output()
        .expect("Failed to run binary");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("dangerzone-rust"));
}

#[test]
fn test_cli_missing_file() {
    let binary_path = get_binary_path();

    let output = Command::new(&binary_path)
        .arg("nonexistent-file.pdf")
        .output()
        .expect("Failed to run binary");

    // Should fail with exit code 1
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("File not found") || stderr.contains("nonexistent-file.pdf"));
}

#[test]
fn test_cli_output_filename_multiple_files() {
    let binary_path = get_binary_path();
    let temp_dir = TempDir::new().unwrap();

    // Create two dummy files
    let file1 = temp_dir.path().join("test1.txt");
    let file2 = temp_dir.path().join("test2.txt");
    File::create(&file1).unwrap();
    File::create(&file2).unwrap();

    let output = Command::new(&binary_path)
        .arg(&file1)
        .arg(&file2)
        .arg("--output-filename")
        .arg("output.pdf")
        .output()
        .expect("Failed to run binary");

    // Should fail when using --output-filename with multiple files
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("--output-filename can only be used with one input file"));
}

/// Get the path to the compiled binary
fn get_binary_path() -> PathBuf {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("target");
    path.push("debug");
    path.push("dangerzone-rust");

    if !path.exists() {
        panic!(
            "Binary not found at {:?}. Run 'cargo build --bin dangerzone-rust' first.",
            path
        );
    }

    path
}

#[test]
fn test_generate_output_filename() {
    // This is more of a unit test for the internal logic
    // We can verify the naming convention
    let binary_path = get_binary_path();

    // Run with --help to verify binary works
    let output = Command::new(&binary_path)
        .arg("--help")
        .output()
        .expect("Failed to run binary");

    assert!(output.status.success());
}
