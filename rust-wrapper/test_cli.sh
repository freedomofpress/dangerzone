#!/bin/bash
# Simple integration test script for dangerzone-rust CLI
# This demonstrates the CLI can be invoked and handles basic scenarios

set -e

BINARY="./target/debug/dangerzone-rust"

echo "Testing dangerzone-rust CLI binary..."
echo "======================================"
echo

# Test 1: Help command
echo "Test 1: Check --help works"
$BINARY --help > /dev/null
echo "✓ Help command works"
echo

# Test 2: Version command
echo "Test 2: Check --version works"
VERSION=$($BINARY --version)
echo "  Version: $VERSION"
echo "✓ Version command works"
echo

# Test 3: Missing file error
echo "Test 3: Check error handling for missing file"
if $BINARY nonexistent-file.pdf 2>&1 | grep -q "File not found"; then
    echo "✓ Correctly reports missing file"
else
    echo "✗ Failed to report missing file"
    exit 1
fi
echo

# Test 4: Multiple files with --output-filename should fail
echo "Test 4: Check --output-filename with multiple files fails"
TEMP_DIR=$(mktemp -d)
touch "$TEMP_DIR/file1.pdf" "$TEMP_DIR/file2.pdf"
if $BINARY "$TEMP_DIR/file1.pdf" "$TEMP_DIR/file2.pdf" --output-filename output.pdf 2>&1 | grep -q "can only be used with one input file"; then
    echo "✓ Correctly rejects --output-filename with multiple files"
else
    echo "✗ Failed to reject --output-filename with multiple files"
    rm -rf "$TEMP_DIR"
    exit 1
fi
rm -rf "$TEMP_DIR"
echo

echo "======================================"
echo "All CLI integration tests passed! ✓"
echo
echo "Note: Full end-to-end conversion tests require a container runtime"
echo "and the dangerzone container image to be available."
