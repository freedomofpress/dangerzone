#!/usr/bin/python3

import logging
import sys
import time

from dangerzone import document
from dangerzone.ctx import ConversionCtx


def main():
    logging.basicConfig(level=logging.INFO)
    doc = document.Document()
    ctx = ConversionCtx(doc)
    ctx.start_conversion_proc()
    ctx.start_page_gathering()
    for page in ctx.page_iter(10):
        time.sleep(0.2)
        if not page % 5:
            ctx.fail(f"Failed during page {page}")

    ctx.success()


if __name__ == "__main__":
    sys.exit(main())
