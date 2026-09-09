# Convert documents from the command line

Dangerzone ships a command-line tool, `dangerzone-cli`, next to the graphical application. In this tutorial you will use it to convert a single document, then a batch of documents with OCR, and archive the originals. This is handy when you have many files, or when you want to automate the conversion process.

You need Dangerzone installed (see the [installation guide](../how-to/install/index.md)) and a terminal. The examples use a folder called `inbox` with a couple of PDFs and office documents in it. Any files from the [supported formats](../reference/supported-formats.md) will do.

## 1. Find the command

The command lives in different places depending on your platform:

=== "Linux"

    `dangerzone-cli` is on your `PATH`:

    ```console
    $ dangerzone-cli --version
    0.11.0
    ```

    !!! note

        With the slim `dangerzone` package, the CLI does not download the sandbox on its own. Either start the graphical application once and accept the download, or run `dangerzone-image upgrade` first.

=== "macOS"

    The tool is inside the application bundle:

    ```console
    $ /Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --version
    0.11.0
    ```

    Define an alias for the rest of this tutorial:

    ```sh
    alias dangerzone-cli=/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli
    ```

=== "Windows"

    The tool is in the installation folder. In a terminal:

    ```powershell
    & 'C:\Program Files\Dangerzone\dangerzone-cli.exe' --version
    ```

    The examples below use `dangerzone-cli` for brevity. Prefix it with the full path, or add `C:\Program Files\Dangerzone` to your `PATH`.

## 2. Convert one document

```console
$ cd inbox
$ dangerzone-cli invoice.pdf
```

Dangerzone prints a banner, starts the sandbox, and shows the progress of each stage. On macOS and Windows, the first run also starts the Podman machine, a small virtual machine that runs the sandbox, which takes a little longer.

When it finishes, `invoice-safe.pdf` sits next to `invoice.pdf`. The original is untouched: unlike the graphical application, the CLI does not move originals unless you ask it to (see "archive" below)

## 3. Choose the output name

Pass `--output-filename` to control where the safe PDF goes. This only works with a single input file:

```console
$ dangerzone-cli invoice.pdf --output-filename ~/Documents/invoice-clean.pdf
```

## 4. Convert a batch with OCR

Give the command several files, and add `--ocr-lang` with a language code so that the safe PDFs get a searchable text layer:

```console
$ dangerzone-cli --ocr-lang eng report.docx slides.pptx scan.jpg
```

Conversions run one after the other and each one reports its own progress. The output files are `report-safe.pdf`, `slides-safe.pdf`, and `scan-safe.pdf`.

If you pass a language code Dangerzone doesn't know, it prints the list of valid codes and exits. `eng`, `fra`, `deu`, `spa`, and `ara` are examples of valid codes.

## 5. Archive the originals

Add `--archive` to move each original into an `unsafe/` subdirectory after a successful conversion, exactly like the graphical application does by default:

```console
$ dangerzone-cli --archive --ocr-lang eng *.pdf
$ ls
report-safe.pdf  scan-safe.pdf  unsafe/
$ ls unsafe
report.pdf  scan.pdf
```

## 6. Keep the machine running between batches (macOS and Windows)

On macOS and Windows, Dangerzone stops the Podman machine after each invocation. If you plan to run several commands in a row, pass `--linger` so the machine stays up, then stop it yourself when you are done:

```console
$ dangerzone-cli --linger first-batch/*.pdf
$ dangerzone-cli --linger second-batch/*.pdf
$ dangerzone-machine stop
```

## What you learned

You can now convert one or many documents from a terminal, name the output, add OCR, and archive the originals. The [dangerzone-cli reference](../reference/cli/dangerzone-cli.md) lists every option, including `--debug` for gVisor logs when something goes wrong.

## Where to go next

* Update the sandbox image by hand, or install it on an air-gapped machine: [Update the sandbox image](../how-to/install/update-the-sandbox.md).
* Manage the Podman machine on macOS and Windows: [dangerzone-machine reference](../reference/cli/dangerzone-machine.md).
