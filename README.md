# dangerzone

Take potentially dangerous PDFs, office documents, or images and convert them to a safe PDF.

![Screenshot](./assets/screenshot.png)

Dangerzone works like this: You give it a document that you don't know if you can trust (for example, an email attachment). Inside of a sandbox, dangerzone converts the document to a PDF (if it isn't already one), and then converts the PDF into raw pixel data: a huge list of of RGB color values for each page. Then, in a separate sandbox, dangerzone takes this pixel data and converts it back into a PDF.

_Read more about dangerzone in the blog post [Dangerzone: Working With Suspicious Documents Without Getting Hacked](https://tech.firstlook.media/dangerzone-working-with-suspicious-documents-without-getting-hacked)._

## Getting started

- Download [dangerzone 0.1.4 for Mac](https://github.com/firstlookmedia/dangerzone/releases/download/v0.1.4/Dangerzone.0.1.4.dmg)
- Download [dangerzone 0.1.4 for Windows](https://github.com/firstlookmedia/dangerzone/releases/download/v0.1.4/Dangerzone.0.1.4.msi)
- See [installing dangerzone](https://github.com/firstlookmedia/dangerzone/wiki/Installing-Dangerzone) on the wiki for Linux repositories

You can also install dangerzone for Mac using [Homebrew](https://brew.sh/): `brew cask install dangerzone`

## Some features

- Sandboxes don't have network access, so if a malicious document can compromise one, it can't phone home
- Dangerzone can optionally OCR the safe PDFs it creates, so it will have a text layer again
- Dangerzone compresses the safe PDF to reduce file size
- After converting, dangerzone lets you open the safe PDF in the PDF viewer of your choice, which allows you to open PDFs and office docs in dangerzone by default so you never accidentally open a dangerous document

Dangerzone can convert these types of document into safe PDFs:

- PDF (`.pdf`)
- Microsoft Word (`.docx`, `.doc`)
- Microsoft Excel (`.xlsx`, `.xls`)
- Microsoft PowerPoint (`.pptx`, `.ppt`)
- ODF Text (`.odt`)
- ODF Spreadsheet (`.ods`)
- ODF Presentation (`.odp`)
- ODF Graphics (`.odg`)
- Jpeg (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- PNG (`.png`)
- TIFF (`.tif`, `.tiff`)

Dangerzone was inspired by [Qubes trusted PDF](https://blog.invisiblethings.org/2013/02/21/converting-untrusted-pdfs-into-trusted.html), but it works in non-Qubes operating systems. It uses containers as sandboxes instead of virtual machines (using Docker for macOS, Windows, and Debian/Ubuntu, and [podman](https://podman.io/) for Fedora).

Set up a development environment by following [these instructions](/BUILD.md).

The git repository for the container is called [dangerzone-converter](https://github.com/firstlookmedia/dangerzone-converter).
