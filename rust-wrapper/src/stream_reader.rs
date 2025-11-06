//! Stream reader for pixel data from container output.
//!
//! This module handles reading and parsing the pixel stream format from container stdout:
//! - Page count (2 bytes, big-endian int)
//! - For each page:
//!   - Page width (2 bytes, big-endian int)
//!   - Page height (2 bytes, big-endian int)
//!   - Page data (width * height * 3 bytes, RGB pixels)

use byteorder::{BigEndian, ReadBytesExt};
use std::io::{self, Read};

/// Represents a page with its dimensions and pixel data.
#[derive(Debug, Clone, PartialEq)]
pub struct PageData {
    pub width: u16,
    pub height: u16,
    pub pixels: Vec<u8>,
}

impl PageData {
    /// Creates a new PageData instance.
    pub fn new(width: u16, height: u16, pixels: Vec<u8>) -> Result<Self, StreamError> {
        let expected_size = (width as usize) * (height as usize) * 3;
        if pixels.len() != expected_size {
            return Err(StreamError::InvalidPixelData {
                expected: expected_size,
                actual: pixels.len(),
            });
        }
        Ok(PageData {
            width,
            height,
            pixels,
        })
    }

    /// Returns the number of pixels in the page.
    pub fn pixel_count(&self) -> usize {
        (self.width as usize) * (self.height as usize)
    }
}

/// Errors that can occur during stream reading.
#[derive(Debug, thiserror::Error)]
pub enum StreamError {
    #[error("IO error: {0}")]
    Io(#[from] io::Error),

    #[error("Invalid page count: {0}")]
    InvalidPageCount(u16),

    #[error("Invalid page dimensions: width={width}, height={height}")]
    InvalidPageDimensions { width: u16, height: u16 },

    #[error("Invalid pixel data: expected {expected} bytes, got {actual}")]
    InvalidPixelData { expected: usize, actual: usize },

    #[error("Unexpected end of stream")]
    UnexpectedEof,
}

/// Reads pixel stream data from a container's stdout.
pub struct PixelStreamReader<R: Read> {
    reader: R,
}

impl<R: Read> PixelStreamReader<R> {
    /// Creates a new PixelStreamReader.
    pub fn new(reader: R) -> Self {
        PixelStreamReader { reader }
    }

    /// Reads the page count from the stream.
    pub fn read_page_count(&mut self) -> Result<u16, StreamError> {
        let count = self.reader.read_u16::<BigEndian>()?;
        if count == 0 {
            return Err(StreamError::InvalidPageCount(count));
        }
        Ok(count)
    }

    /// Reads a single page from the stream.
    pub fn read_page(&mut self) -> Result<PageData, StreamError> {
        let width = self.reader.read_u16::<BigEndian>()?;
        let height = self.reader.read_u16::<BigEndian>()?;

        if width == 0 || height == 0 {
            return Err(StreamError::InvalidPageDimensions { width, height });
        }

        let num_bytes = (width as usize) * (height as usize) * 3;
        let mut pixels = vec![0u8; num_bytes];
        self.reader.read_exact(&mut pixels).map_err(|e| {
            if e.kind() == io::ErrorKind::UnexpectedEof {
                StreamError::UnexpectedEof
            } else {
                StreamError::Io(e)
            }
        })?;

        Ok(PageData {
            width,
            height,
            pixels,
        })
    }

    /// Reads all pages from the stream.
    pub fn read_all_pages(&mut self) -> Result<Vec<PageData>, StreamError> {
        let page_count = self.read_page_count()?;
        let mut pages = Vec::with_capacity(page_count as usize);

        for _ in 0..page_count {
            pages.push(self.read_page()?);
        }

        Ok(pages)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn create_test_stream(page_count: u16, pages: Vec<(u16, u16, Vec<u8>)>) -> Vec<u8> {
        let mut data = Vec::new();
        data.extend_from_slice(&page_count.to_be_bytes());

        for (width, height, pixels) in pages {
            data.extend_from_slice(&width.to_be_bytes());
            data.extend_from_slice(&height.to_be_bytes());
            data.extend_from_slice(&pixels);
        }

        data
    }

    #[test]
    fn test_read_page_count() {
        let data = vec![0x00, 0x05]; // 5 pages
        let mut reader = PixelStreamReader::new(Cursor::new(data));
        assert_eq!(reader.read_page_count().unwrap(), 5);
    }

    #[test]
    fn test_read_page_count_zero() {
        let data = vec![0x00, 0x00]; // 0 pages
        let mut reader = PixelStreamReader::new(Cursor::new(data));
        assert!(matches!(
            reader.read_page_count(),
            Err(StreamError::InvalidPageCount(0))
        ));
    }

    #[test]
    fn test_read_single_page() {
        let width = 2u16;
        let height = 2u16;
        let pixels = vec![
            255, 0, 0, // red pixel
            0, 255, 0, // green pixel
            0, 0, 255, // blue pixel
            255, 255, 0, // yellow pixel
        ];

        let data = create_test_stream(1, vec![(width, height, pixels.clone())]);
        let mut reader = PixelStreamReader::new(Cursor::new(data));

        let page_count = reader.read_page_count().unwrap();
        assert_eq!(page_count, 1);

        let page = reader.read_page().unwrap();
        assert_eq!(page.width, width);
        assert_eq!(page.height, height);
        assert_eq!(page.pixels, pixels);
    }

    #[test]
    fn test_read_multiple_pages() {
        let pages_data = vec![
            (2u16, 2u16, vec![255u8; 12]), // 2x2 page with white pixels
            (3u16, 3u16, vec![0u8; 27]),   // 3x3 page with black pixels
        ];

        let data = create_test_stream(2, pages_data.clone());
        let mut reader = PixelStreamReader::new(Cursor::new(data));

        let pages = reader.read_all_pages().unwrap();
        assert_eq!(pages.len(), 2);

        assert_eq!(pages[0].width, 2);
        assert_eq!(pages[0].height, 2);
        assert_eq!(pages[0].pixels.len(), 12);

        assert_eq!(pages[1].width, 3);
        assert_eq!(pages[1].height, 3);
        assert_eq!(pages[1].pixels.len(), 27);
    }

    #[test]
    fn test_invalid_page_dimensions() {
        let data = create_test_stream(1, vec![(0, 100, vec![])]);
        let mut reader = PixelStreamReader::new(Cursor::new(data));
        reader.read_page_count().unwrap();

        assert!(matches!(
            reader.read_page(),
            Err(StreamError::InvalidPageDimensions { .. })
        ));
    }

    #[test]
    fn test_incomplete_pixel_data() {
        let mut data = Vec::new();
        data.extend_from_slice(&1u16.to_be_bytes()); // page count
        data.extend_from_slice(&2u16.to_be_bytes()); // width
        data.extend_from_slice(&2u16.to_be_bytes()); // height
        data.extend_from_slice(&[255u8; 6]); // Only 6 bytes instead of 12

        let mut reader = PixelStreamReader::new(Cursor::new(data));
        reader.read_page_count().unwrap();

        assert!(matches!(
            reader.read_page(),
            Err(StreamError::UnexpectedEof)
        ));
    }

    #[test]
    fn test_page_data_new() {
        let pixels = vec![255u8; 12]; // 2x2 page = 12 bytes
        let page = PageData::new(2, 2, pixels).unwrap();
        assert_eq!(page.width, 2);
        assert_eq!(page.height, 2);
        assert_eq!(page.pixel_count(), 4);
    }

    #[test]
    fn test_page_data_new_invalid_size() {
        let pixels = vec![255u8; 10]; // Wrong size
        let result = PageData::new(2, 2, pixels);
        assert!(matches!(
            result,
            Err(StreamError::InvalidPixelData {
                expected: 12,
                actual: 10
            })
        ));
    }
}
