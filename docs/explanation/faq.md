# Frequently asked questions

## What is a "safe PDF"?

A PDF that Dangerzone rebuilt from pictures of each page of the original. It contains only those pictures and — if you enabled <abbr title="Optical Character Recognition">OCR</abbr> — a text layer. That removes any script, embedded files or logic that was present in the original document. See [How Dangerzone works](how-dangerzone-works.md).

## Can Dangerzone tell me whether a file is malicious?

No. Unfortunately, dangerzone can't tell you if a file is safe, it just creates a copy that is.

## What is OCR, and why does Dangerzone ask for a language?

OCR stands for "Optical Character Recognition": a software that reads the text in a picture. It is used in Dangerzone in order to add an invisible text layer, which will make the documents searchable, and copy-pastable. OCR works much better when it knows which language to expect, hence the language choice.

## Does Dangerzone remove watermarks and tracking information?

It depends on where the information lives.

* **Metadata** (author, software, file creation dates, camera model, GPS coordinates, editing history) is removed as part of the process.
* **Hidden document structure** (comments, embedded files, scripts, links) is also removed.
* **Anything visible on the page** will not be removed. And so, visible watermarks, printer tracking dots, unusual spacing, unique wording, or steganography hidden in the image will not be removed. If you are a source, treat this as a separate risk that Dangerzone does not address. See [When should I use Dangerzone?](when-to-use-dangerzone.md).

## Is there a command-line version?

Yes. `dangerzone-cli` is installed next to the graphical application on every platform, and can convert files from the terminal. See [Convert documents from the command line](../tutorials/convert-from-the-command-line.md) and the [dangerzone-cli reference](../reference/cli/dangerzone-cli.md).

## Why not just open PDFs in Firefox, which has its own sandbox?

Browser viewers such as `PDF.js` render the PDF inside the browser's sandbox, which does contain many attacks. Two differences remain. First, the PDF is still the original file: once you save or forward it, the next person gets every script and link it carried. Second, browser sandboxes are a target in their own right and escapes are found regularly. Dangerzone gives you a new file that is safe in any viewer, produced in a sandbox that runs nothing else and has no network.

## Isn't this overkill for everyday use?

For files you trust, yes. Dangerzone is aimed at people who regularly open files from strangers, such as journalists, lawyers and researchers (or anyone handling one specific suspicious file, really). Converting takes seconds for a short PDF and the result is heavier and less editable than the original. Use it where the risk is, and see [When should I use Dangerzone?](when-to-use-dangerzone.md) for the cases where it isn't the right tool.

## Why would I convert a JPG or PNG? They are just pictures.

Image formats are decoded by complex libraries, and those libraries have had serious vulnerabilities in the past. Exploits delivered through crafted images, including PNG and SVG files, have been used in the wild. Dangerzone decodes the image inside the sandbox and re-encodes only the pixels. It also strips image metadata, such as camera model and GPS coordinates, which is often what people want when sharing a picture.

## Why is the safe PDF so large?

Every page is stored as an image. Dangerzone compresses the result, but a picture of a page of text is still larger than the text itself. Long documents with OCR take the longest and produce the biggest files.

## Has Dangerzone received a security audit?

Yes, Dangerzone received its [first security audit](https://freedom.press/news/dangerzone-receives-favorable-audit/) by [Include Security](https://includesecurity.com/) in December 2023. The audit was generally favorable, as it didn't identify any high-risk findings, except for 3 low-risk and 7 informational findings.

## Can I run Dangerzone in an airgapped environment?

Yes, Dangerzone is designed to run in airgapped environments without any configuration. If you want to update its container image, follow [our instructions](../how-to/install/update-the-sandbox.md#installing-image-updates-to-air-gapped-environments).

## Can I use a custom runtime, such as Podman Desktop?

On Windows and macOS, Dangerzone embeds Podman, so there is no need to.

To use a different podman version, such as Podman Desktop, [follow our documentation](../how-to/install/use-podman-desktop.md).

## "I'm experiencing an issue while using Dangerzone."

First, [make sure you use the latest version of Dangerzone](../how-to/install/update-dangerzone.md).

If the problem persists, please [report it](../how-to/contribute/report-an-issue.md).

## Why does Dangerzone need to download something on first start?

The sandbox is a container image of a few hundred megabytes. On macOS and Windows it is bundled in the installer. On Linux, the slim `dangerzone` package downloads it on first use so that the package itself stays small and the sandbox can be updated independently. The `dangerzone-full` package bundles it instead. See [Independent sandbox updates](sandbox-updates.md).

## Which platforms and document formats are supported?

See [Supported platforms](../reference/supported-platforms.md) and [Supported document formats](../reference/supported-formats.md).
