# Frequently asked questions

Short answers to questions that come up often, with pointers to the pages
that go into detail.

## What does "safe PDF" mean?

A PDF that Dangerzone rebuilt from pictures of each page of the original. It
contains only those pictures and, if you enabled OCR, a text layer that
Dangerzone itself produced. Scripts, links, embedded files, form logic, and
metadata from the original don't make it through. See
[How Dangerzone works](how-dangerzone-works.md).

## Can Dangerzone tell me whether a file is malicious?

No. Dangerzone can't tell you if a file is safe. It just creates a copy that
is. A successful conversion says nothing about the original. A failed
conversion usually means the file is corrupted or unsupported. It is no sign
of malice either.

## What is OCR, and why does Dangerzone ask for a language?

OCR stands for optical character recognition: software that reads the text in
a picture. Because the safe PDF is made of pictures, its text would otherwise
be unsearchable and impossible to copy. With OCR enabled, Dangerzone adds an
invisible text layer so that you can search and select text again. OCR works
much better when it knows which language to expect, hence the language
choice. It is never perfect, especially on scans and unusual fonts.

## Does Dangerzone remove watermarks and tracking information?

It depends on where the information lives.

* **Metadata** (author, software, dates, camera, GPS, editing history): yes,
  all of it is gone.
* **Hidden document structure** (comments, tracked changes, hidden layers,
  embedded files, scripts, links): yes, gone.
* **Anything visible on the page**: no. Visible watermarks, printer tracking
  dots, unusual spacing, unique wording, or steganography hidden in an image
  are part of the picture, and the picture is exactly what Dangerzone keeps.
  Comparing two copies of a "same" document can reveal such differences. If
  you are a source, treat this as a separate risk that Dangerzone does not
  address. See [When should I use Dangerzone?](when-to-use-dangerzone.md).

## Is there a command-line version?

Yes. `dangerzone-cli` is installed next to the graphical application on every
platform, and converts one or many files from a terminal. See
[Convert documents from the command line](../tutorials/convert-from-the-command-line.md)
and the [dangerzone-cli reference](../reference/cli/dangerzone-cli.md).

## Why not just open PDFs in Firefox, which has its own sandbox?

Browser viewers such as PDF.js render the PDF inside the browser's sandbox,
which does contain many attacks. Two differences remain. First, the PDF is
still the original file: once you save or forward it, the next person gets
every script and link it carried. Second, browser sandboxes are a target in
their own right and escapes are found regularly. Dangerzone gives you a new
file that is safe in any viewer, produced in a sandbox that runs nothing else
and has no network.

## Isn't this overkill for everyday use?

For files you trust, yes. Dangerzone is aimed at people who regularly open
files from strangers, such as journalists, lawyers, and researchers, and at
anyone handling one specific suspicious file. Converting takes seconds for a
short PDF and the result is heavier and less editable than the original. Use
it where the risk is, and see [When should I use Dangerzone?](when-to-use-dangerzone.md)
for the cases where it isn't the right tool.

## Why would I convert a JPG or PNG? They are just pictures.

Image formats are decoded by complex libraries, and those libraries have had
serious vulnerabilities. Exploits delivered through crafted images, including
PNG and SVG files, have been used in the wild. Dangerzone decodes the image
inside the sandbox and re-encodes only the pixels. It also strips image
metadata, such as camera model and GPS coordinates, which is often what
people want when sharing a photograph.

## Why is the safe PDF so large?

Every page is stored as an image. Dangerzone compresses the result, but a
picture of a page of text is still larger than the text itself. Long
documents with OCR take the longest and produce the biggest files.

## Has Dangerzone received a security audit?

Yes, Dangerzone received its [first security audit](https://freedom.press/news/dangerzone-receives-favorable-audit/) by [Include Security](https://includesecurity.com/) in December 2023. The audit was generally favorable, as it didn't identify any high-risk findings, except for 3 low-risk and 7 informational findings.

## Can I run Dangerzone in an airgapped environment?

Yes, Dangerzone is designed to run in airgapped environments without any
configuration. If you want to update its container image, follow
[our instructions](../how-to/update-the-sandbox.md#installing-image-updates-to-air-gapped-environments).

## Can I use a custom runtime, such as Podman Desktop?

On Windows and macOS, Dangerzone embeds Podman, so there is no need to.

To use a different podman version, such as Podman Desktop, [follow our documentation](../how-to/use-podman-desktop.md).

## "I'm experiencing an issue while using Dangerzone."

Dangerzone gets updates to improve its features _and_ to fix problems. So, updating may be the simplest path to resolving the issue which brought you here. Here is how to update:

1. Check which version of Dangerzone you are currently using: run Dangerzone, then look for a series of numbers to the right of the logo within the app. The format of the numbers will look similar to `0.4.1`
2. Now find the latest available version of Dangerzone: go to the [download page](https://dangerzone.rocks/#downloads). Look for the version number displayed. The number will be using the same format as in Step 1.
3. Is the version on the Dangerzone download page higher than the version of your installed app? Go ahead and update.

If the problem persists, [report it](../how-to/report-an-issue.md).

## Why does Dangerzone need to download something on first start?

The sandbox is a container image of a few hundred megabytes. On macOS and
Windows it is bundled in the installer. On Linux, the slim `dangerzone`
package downloads it on first use so that the package itself stays small and
the sandbox can be updated independently. The `dangerzone-full` package bundles
it instead. See [Independent sandbox updates](sandbox-updates.md).

## Which platforms and document formats are supported?

See [Supported platforms](../reference/supported-platforms.md) and
[Supported document formats](../reference/supported-formats.md).
