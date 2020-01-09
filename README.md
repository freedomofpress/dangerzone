# dangerzone

Take potentially dangerous PDFs, office documents, or images and convert them to a safe PDF.

_This is a work in progress and is not quite ready for daily use yet._

![Screenshot](./assets/screenshot.png)

Dangerzone works like this: You give it a document that you don't know if you can trust (for example, an email attachment). Inside of a sandbox, dangerzone converts the document to a PDF (if it isn't already one), and then converts the PDF into raw pixel data: a huge list of of RGB color values for each page. Then, in a separate sandbox, dangerzone takes this pixel data and converts it back into a PDF.

Some features:

- Sandboxes don't have network access, so if a malicious document can compromise one, it can't phone home
- Dangerzone can optionally OCR the safe PDFs it creates, so it will have a text layer again
- Dangerzone compresses the safe PDF to reduce file size
- After converting, dangerzone lets you open the safe PDF in the PDF viewer of your choice, which allows you to open PDFs and office docs in dangerzone by default so you never accidentally open a dangerous document

Dangerzone was inspired by [Qubes trusted PDF](https://blog.invisiblethings.org/2013/02/21/converting-untrusted-pdfs-into-trusted.html), but it works in non-Qubes operating systems and sandboxes the document conversion in containers instead of virtual machines (using [podman](https://podman.io/) for Linux, and Docker for macOS, for now). Podman is like docker but more secure -- it doesn't require a privileged daemon, and containers can be launched without root.

Set up a development environment by following [these instructions](/BUILD.md).
