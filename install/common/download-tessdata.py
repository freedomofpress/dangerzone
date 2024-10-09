import hashlib
import io
import json
import logging
import pathlib
import subprocess
import sys
import tarfile
import urllib.request

logger = logging.getLogger(__name__)

TESSDATA_RELEASES_URL = (
    "https://api.github.com/repos/tesseract-ocr/tessdata_fast/releases/latest"
)
TESSDATA_ARCHIVE_URL = "https://github.com/tesseract-ocr/tessdata_fast/archive/{tessdata_version}/tessdata_fast-{tessdata_version}.tar.gz"
TESSDATA_CHECKSUM = "d0e3bb6f3b4e75748680524a1d116f2bfb145618f8ceed55b279d15098a530f9"


def git_root():
    """Get the root directory of the Git repo."""
    # FIXME: Use a Git Python binding for this.
    # FIXME: Make this work if called outside the repo.
    cmd = ["git", "rev-parse", "--show-toplevel"]
    path = (
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
        .stdout.decode()
        .strip("\n")
    )
    return pathlib.Path(path)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    share_dir = git_root() / "share"
    tessdata_dir = share_dir / "tessdata"

    # Get the list of OCR languages that Dangerzone supports.
    with open(share_dir / "ocr-languages.json") as f:
        langs_short = sorted(json.loads(f.read()).values())

    # Check if these languages have already been downloaded.
    if tessdata_dir.exists():
        expected_files = {f"{lang}.traineddata" for lang in langs_short}
        files = {f.name for f in tessdata_dir.iterdir()}
        if files == expected_files:
            logger.info("Skipping tessdata download, language data already exists")
            return
        else:
            logger.info(f"Found {tessdata_dir} but contents do not match")
            return 1

    # Get latest release of Tesseract data.
    logger.info("Getting latest tessdata release")
    with urllib.request.urlopen(TESSDATA_RELEASES_URL) as f:
        resp = f.read()
        releases = json.loads(resp)
        tag = releases["tag_name"]

    # Get latest release of Tesseract data.
    logger.info(f"Downloading tessdata release {tag}")
    archive_url = TESSDATA_ARCHIVE_URL.format(tessdata_version=tag)
    with urllib.request.urlopen(archive_url) as f:
        archive = f.read()
        digest = hashlib.sha256(archive).hexdigest()
        if digest != TESSDATA_CHECKSUM:
            raise RuntimeError(f"Checksum mismatch {digest} != {TESSDATA_CHECKSUM}")

    # Extract the languages models from the tessdata archive.
    logger.info(f"Extracting tessdata archive into {tessdata_dir}")
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        for lang in langs_short:
            member = f"tessdata_fast-{tag}/{lang}.traineddata"
            logger.info(f"Extracting {member}")

    tessdata_dl_dir = share_dir / f"tessdata_fast-{tag}"
    tessdata_dl_dir.rename(tessdata_dir)


if __name__ == "__main__":
    sys.exit(main())
