# What is Dangerzone?

Dangerzone is a desktop application that takes potentially dangerous PDFs,
office documents, or images and converts them to a safe PDF. This page is
written for people who want to understand the idea without the technical
detail. [How Dangerzone works](how-dangerzone-works.md) goes deeper, and
[When should I use Dangerzone?](when-to-use-dangerzone.md) helps you decide
whether it fits a given situation.

## The problem it solves

Opening a document is more dangerous than it looks. A PDF, a Word file, or
even an image is a complex thing that your computer has to interpret, and
every piece of software that interprets documents has had bugs that let a
carefully crafted file take over the computer that opens it. Such files look
perfectly normal. There is no way to tell a booby-trapped document from a
harmless one by looking at it, and antivirus software only catches what it
has seen before.

This matters most for people who, as part of their work, open documents from
strangers: journalists who receive tips, lawyers, human rights workers, anyone
with a public inbox.

## The idea

Think of a document as something you can only safely look at through a
window. Dangerzone opens the document in a sealed room (a *sandbox*), takes a
photograph of every page, and hands you the photographs. The room is then
thrown away, together with whatever the document did inside it.

The photographs, assembled into a new PDF, contain only the picture of each
page. No scripts, no links, no hidden objects, no metadata from the original.
If you turn on *OCR* (optical character recognition), Dangerzone also reads
the text in the pictures so that you can still search and copy it.

Dangerzone can't tell you if a file is safe. It just creates a copy that is.

## Dangerzone for journalists

Dangerzone was built with journalists in mind, and is maintained by the
[Freedom of the Press Foundation](https://freedom.press). A few points from
the [journalists' page](https://dangerzone.rocks/journalists/) on the official
site are worth repeating here:

* Dangerzone can't tell you if a file is safe. It just creates a copy that is.
* Just like printing a file, it doesn't preserve formulas in a spreadsheet, or
  macros in a Word document.
* It doesn't neutralize visual information, like
  [printer tracking dots](https://en.wikipedia.org/wiki/Printer_tracking_dots),
  or [steganography](https://en.wikipedia.org/wiki/Steganography), which could
  contain identifying information. To protect your sources, consider these
  risk factors separately.

Dangerzone is also part of the tooling around
[SecureDrop](https://securedrop.org/), and ships in
[Tails](https://tails.net/doc/persistent_storage/additional_software/dangerzone/index.en.html)
as additional software. Read about how newsrooms use it in
[GIJN's toolbox](https://gijn.org/stories/cutting-edge-free-online-investigative-tools/)
and the Guardian's
[account of working with Qubes OS](https://www.theguardian.com/info/2024/apr/04/when-security-matters-working-with-qubes-os-at-the-guardian).

## Similar projects

Dangerzone sits next to a few other tools. Knowing what each one does helps
you pick the right one:

* **[Qubes trusted PDF](https://blog.invisiblethings.org/2013/02/21/converting-untrusted-pdfs-into-trusted.html)**
  (`qvm-convert-pdf`) is the direct inspiration: the same document-to-pixels
  idea, using Qubes OS disposable virtual machines. Dangerzone brings it to
  macOS, Windows, and regular Linux, and integrates with Qubes OS as well.
* **[mat2](https://0xacab.org/jvoisin/mat2)** and its graphical front-end
  **[Metadata Cleaner](https://metadatacleaner.romainvigier.fr/)** remove
  metadata from files while keeping the file format and editability. They
  don't protect you from a malicious file. Use them when you want to send a
  file you trust, in its original format, without your name in it. Use
  Dangerzone when you receive a file you don't trust, or when you want to be
  sure nothing else is hiding in it.
* **Browser PDF viewers** such as Firefox's PDF.js open PDFs inside the
  browser's sandbox. That contains many attacks, but the PDF itself keeps
  every feature, and browser sandbox escapes happen. Dangerzone produces a
  file you can keep and share safely afterwards, with any viewer.
* **Print to PDF** or taking screenshots by hand achieves a similar result for
  one document, using your normal viewer to open the dangerous file. That is
  the step Dangerzone does for you, inside a sandbox, for many files at once.

See the [FAQ](faq.md) for more comparisons and common questions.
