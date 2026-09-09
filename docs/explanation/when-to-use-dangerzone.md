# When should I use Dangerzone?

Dangerzone is the right tool for some situations and the wrong tool for others. The short rule:

!!! tip "Rule of thumb"

    Always use Dangerzone on text or image files you received from an external source. Exceptions are for video or audio file (they are not supported at the moment), or if you need to keep editing the document, as passing it to Dangerzone will transform them to PDFs.

## Decision guide

```mermaid
flowchart TD
    A[What do you want to do with the file?] --> B[Open a file you received]
    A --> C[Send a file to someone]
    A --> D[Continue editing a file you received]

    B --> B1{Is it video or audio?}
    B1 -->|Yes| B2[Dangerzone can't help.<br/>Open it with caution.]
    B1 -->|No, it's text or image| B3[Use Dangerzone]

    C --> C1{Is it video or audio?}
    C1 -->|Yes| C2[Use Metadata Cleaner or mat2]
    C1 -->|No, it's text or image| C3[Use Dangerzone]

    D --> D2[Dangerzone can't help.<br/>Open it with caution.]
```

## Use Dangerzone when...

* **You received a document or an image and want to open it.** This is the main use case: an email attachment, a file from a tip line, a download from a site you don't fully trust. Dangerzone will render any malware or tracking in there ineffective.
* **You want to remove the metadata from a document.** The safe PDF carries none of the original metadata: no author name, no editing history, no camera model, no GPS position, nothing. Actually, if the document contained comments not rendered, they will fade away as well.
* **You move a document from an untrusted environment to a trusted one.** For example from a machine used to browse the web to a machine that holds sensitive material. Converting on the way in keeps the trusted side clean.

## Don't use Dangerzone when...

* **You need to keep editing the document.** Dangerzone rasterizes the file: the result is a picture of each page. This will remove formulas in a spreadhseet or macros in a World document (that's actually the whole point!). If you must edit a document you don't trust, your best chance is probably to do it in a disposable environment instead.
* **The file is video or audio.** Dangerzone only handles documents and images (see [supported formats](../reference/supported-formats.md)). For removing metadata from media files, use [Metadata Cleaner](https://gitlab.com/metadatacleaner/metadatacleaner) or [mat2](https://github.com/jvoisin/mat2). For opening untrusted media, there is no Dangerzone equivalent. Your best chance is probably to do it in a disposable environment instead.
* **You want to know whether a file is malicious.** Dangerzone can't tell you if a file is safe. It just creates a copy that is. (Sorry, malware detection is another story)
* **You need to protect a source from fingerprinting of the document's content.** Dangerzone removes metadata and the file's structure, but doesn't change what is visible on the page: printer tracking dots, watermarks, unique wording, or steganography all survive because they are part of the picture. See the [FAQ](faq.md#does-dangerzone-remove-watermarks-and-tracking-information).

## Examples

| Situation | What to do |
| --------- | ---------- |
| A source emails you a PDF | Use Dangerzone, then read the safe PDF |
| A colleague sends a spreadsheet you need to work on | Don't use Dangerzone. Open it in a disposable environment if you don't trust it |
| You photographed a document and want to publish it | Use Dangerzone to drop the camera metadata, after checking the picture itself for identifying details |
| Someone sends you a voice recording | Dangerzone can't help. Use Metadata Cleaner if you only need to strip metadata before sharing it |
| You downloaded a scanned form to print and sign | Use Dangerzone, then print the safe PDF |
