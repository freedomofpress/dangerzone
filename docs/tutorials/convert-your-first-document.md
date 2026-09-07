# Convert your first document

In this tutorial you will install Dangerzone, open a document you don't fully
trust, and turn it into a safe PDF. By the end you will know what the
application looks like, where the safe file ends up, and what happens to the
original.

You need a computer running macOS, Windows, or a supported Linux
distribution, an internet connection for the installation, and a document to
convert. Any PDF, office document, or image works. If you have nothing at hand,
a PDF you downloaded from the web is a fine candidate.

## 1. Install Dangerzone

Follow the installation guide for your platform, then come back here:

* [macOS](../how-to/install.md#macos) (download the `.dmg`, or
  `brew install --cask dangerzone` if you use Homebrew)
* [Windows](../how-to/install.md#windows) (download the `.msi`, or
  `winget install FreedomofthePressFoundation.Dangerzone`)
* [Ubuntu and Debian](../how-to/install.md#ubuntu-debian)
* [Fedora](../how-to/install.md#fedora)

Qubes OS and Tails users can follow along as well, using the
[Qubes OS](../how-to/install.md#qubes-os) and [Tails](../how-to/install.md#tails)
guides. The screens differ slightly on those platforms.

## 2. Start Dangerzone for the first time

Launch Dangerzone from your applications menu.

The first time it starts, Dangerzone needs a *sandbox*: a container image that
holds the tools used to open documents. What you see depends on how you
installed it:

* On macOS and Windows, and with the `dangerzone-full` Linux packages, the
  sandbox is bundled. Dangerzone installs it and moves on.
* With the slim `dangerzone` Linux packages, a dialog titled
  **Download conversion sandbox?** asks whether Dangerzone may download the
  sandbox from the internet. Click **Yes, download sandbox and enable
  updates**. The download is a few hundred megabytes and only happens once.

If the sandbox was bundled, Dangerzone asks the same question on the second
start instead, with a dialog titled **Enable automatic sandbox updates?**. Click
**Yes, enable sandbox updates** so that Dangerzone keeps the sandbox up to date
and tells you when a new Dangerzone release is out. You can change your mind
later from the hamburger menu in the top-right corner. See
[update notifications](../explanation/update-notifications.md) for what this
setting does and does not do.

Wait until the status bar at the bottom of the window stops reporting startup
work. The main window then shows a large **Select suspicious documents ...**
button.

## 3. Choose the document

Click **Select suspicious documents ...** and pick your document. You can also
drag and drop one or more files onto the window.

The window switches to the settings view. It shows how many documents you
selected and a **Change Selection** button if you picked the wrong one.

## 4. Review the settings

Leave the defaults for this first conversion, and simply read what they do:

* **Save as** shows the name of the output. The safe file gets the same name as
  the original with a `-safe.pdf` suffix, so `report.docx` becomes
  `report-safe.pdf`.
* **Move original documents to 'unsafe' subdirectory** is selected. After the
  conversion, the original is moved into an `unsafe/` folder next to the safe
  PDF, so that you don't open it by accident later.
* **Save safe PDFs to** lets you pick another output folder instead.
* **Open safe documents after converting** opens the result in your PDF viewer
  once it is ready. On Linux you can pick which viewer to use.
* **OCR document language** is checked, with English selected. OCR (optical
  character recognition) reads the text in the page images and adds an
  invisible text layer to the safe PDF, so you can still search and copy
  text. It works best when it knows the language, so pick your document's
  language from the list if it isn't English.

## 5. Convert

Click **Convert to Safe Document**.

Dangerzone opens the document inside the sandbox, renders every page to raw
pixels, then rebuilds a PDF from those pixels outside the sandbox. A progress
bar shows each stage. A one-page PDF takes a few seconds. A long office
document with OCR takes longer.

When it is done, the document row shows a green check mark, and your PDF viewer
opens the safe PDF if you left that setting on.

## 6. Look at the result

Open the folder that contains the original document. You will find:

* `<name>-safe.pdf`: the safe PDF. This is the file you can share, print, or
  keep.
* `unsafe/<name>`: the original, moved out of the way.

Open the safe PDF and check that all pages are there and that you can select
text. Because the PDF was rebuilt from pixels, links, forms, and embedded
scripts from the original are gone. That is the point.

## What you learned

You have installed Dangerzone, let it fetch its sandbox, and converted a
document while keeping the original archived. Every later conversion follows
the same three steps: select, review settings, convert.

## Where to go next

* Convert several documents at once from a terminal:
  [Convert documents from the command line](convert-from-the-command-line.md).
* Understand what happens inside the sandbox:
  [How Dangerzone works](../explanation/how-dangerzone-works.md).
* See the full list of [supported document formats](../reference/supported-formats.md).
