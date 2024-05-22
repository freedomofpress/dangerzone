#!/usr/bin/env python3

import argparse
import getpass
import logging
import os
import sys

import requests

log = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def get_latest_draft_release(token):
    url = "https://api.github.com/repos/freedomofpress/dangerzone/releases"
    headers = DEFAULT_HEADERS.copy()
    headers.update(get_auth_header(token))

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    draft_releases = [release["id"] for release in r.json() if release["draft"]]
    if len(draft_releases) > 1:
        raise RuntimeError("Found more than one draft releases")
    elif len(draft_releases) == 0:
        raise RuntimeError("No draft releases have been found")

    return draft_releases[0]


def get_release_from_tag(token, tag):
    url = f"https://api.github.com/repos/freedomofpress/dangerzone/releases/tags/v{tag}"
    headers = DEFAULT_HEADERS.copy()
    headers.update(get_auth_header(token))

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    return r.json()["id"]


def upload_asset(token, release_id, path):
    filename = os.path.basename(path)
    url = f"https://uploads.github.com/repos/freedomofpress/dangerzone/releases/{release_id}/assets?name={filename}"
    headers = DEFAULT_HEADERS.copy()
    headers.update(get_auth_header(token))
    headers["Content-Type"] = "application/octet-stream"

    with open(path, "rb") as f:
        data = f.read()
        # XXX: We have to load the data in-memory. Another solution is to use multipart
        # encoding, but this doesn't work for GitHub.
        r = requests.post(url, headers=headers, data=data)
        r.raise_for_status()


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Dev script for uploading assets to a GitHub release",
    )
    parser.add_argument(
        "--token",
        help="the file path to the GitHub token we will use for uploading assets",
    )
    parser.add_argument(
        "--tag",
        help=f"use the release with this tag",
    )
    parser.add_argument(
        "--release-id",
        help=f"use the release with this ID",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help=f"use the latest draft release",
    )
    parser.add_argument(
        "file",
        help="the file path to the asset we want to upload",
    )
    args = parser.parse_args()

    setup_logging()

    if args.token:
        log.debug(f"Reading token from {args.token}")
        with open(args.token) as f:
            token = f.read().strip()
    else:
        token = getpass.getpass("Token: ")

    if args.tag:
        log.debug(f"Getting the ID of the {args.tag} release")
        release_id = get_release_from_tag(token, args.tag)
        log.debug(f"The {args.tag} release has ID '{release_id}'")
    elif args.release_id:
        release_id = args.release_id
    else:
        log.debug(f"Getting the ID of the latest draft release")
        release_id = get_latest_draft_release(token)
        log.debug(f"The latest draft release has ID '{release_id}'")

    log.info(f"Uploading file '{args.file}' to GitHub release '{release_id}'")
    upload_asset(token, release_id, args.file)
    log.info(
        f"Successfully uploaded file '{args.file}' to GitHub release '{release_id}'"
    )


if __name__ == "__main__":
    sys.exit(main())
