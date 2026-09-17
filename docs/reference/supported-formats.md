# Supported document formats

Dangerzone can convert these types of document into safe PDFs:

- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Microsoft Excel (`.xlsx`, `.xls`)
- Microsoft PowerPoint (`.pptx`, `.ppt`)
- ODF Text (`.odt`)
- ODF Spreadsheet (`.ods`)
- ODF Presentation (`.odp`)
- ODF Graphics (`.odg`)
- Hancom HWP (Hangul Word Processor) (`.hwp`, `.hwpx`)
    * Not supported on [Qubes OS](https://github.com/freedomofpress/dangerzone/issues/494)
- EPUB (`.epub`)
- Jpeg (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- PNG (`.png`)
- SVG (`.svg`)
- other image formats (`.bmp`, `.pnm`, `.pbm`, `.ppm`, `.tif`, `.tiff`)

The output is always a PDF. Its name is the input name with a `-safe.pdf` suffix, unless you choose otherwise. See [How Dangerzone works](../explanation/how-dangerzone-works.md).

## OCR languages

OCR is performed with Tesseract. The graphical application lists the languages by name. The command-line tool takes Tesseract language codes with `--ocr-lang`, for example `eng`, `fra`, `deu`, `spa`, `ara`, `chi_sim`, or `jpn`. Passing an unknown code prints the full list of accepted codes. The mapping between names and codes is in `share/ocr-languages.json` in the source tree.
