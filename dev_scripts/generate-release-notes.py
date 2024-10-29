#!/usr/bin/env python3

import argparse
import asyncio
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

REPOSITORY = "https://github.com/freedomofpress/dangerzone/"
TEMPLATE = "- {title} ([#{number}]({url}))"


def parse_version(version: str) -> Tuple[int, int]:
    """Extract major.minor from version string, ignoring patch"""
    match = re.match(r"v?(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return (int(match.group(1)), int(match.group(2)))


async def get_last_minor_release(
    client: httpx.AsyncClient, owner: str, repo: str
) -> Optional[str]:
    """Get the latest minor release date (ignoring patches)"""
    response = await client.get(f"https://api.github.com/repos/{owner}/{repo}/releases")
    response.raise_for_status()
    releases = response.json()

    if not releases:
        return None

    # Get the latest minor version by comparing major.minor numbers
    current_version = parse_version(releases[0]["tag_name"])
    latest_date = None

    for release in releases:
        try:
            version = parse_version(release["tag_name"])
            if version < current_version:
                latest_date = release["published_at"]
                break
        except ValueError:
            continue

    return latest_date


async def get_issue_details(
    client: httpx.AsyncClient, owner: str, repo: str, issue_number: int
) -> Optional[dict]:
    """Get issue title and number if it exists"""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    )
    if response.is_success:
        data = response.json()
        return {
            "title": data["title"],
            "number": data["number"],
            "url": data["html_url"],
        }
    return None


def extract_issue_number(pr_body: Optional[str]) -> Optional[int]:
    """Extract issue number from PR body looking for common formats like 'Fixes #123' or 'Closes #123'"""
    if not pr_body:
        return None

    patterns = [
        r"(?:closes|fixes|resolves)\s*#(\d+)",
        r"(?:close|fix|resolve)\s*#(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, pr_body.lower())
        if match:
            return int(match.group(1))

    return None


async def verify_commit_in_master(
    client: httpx.AsyncClient, owner: str, repo: str, commit_id: str
) -> bool:
    """Verify if a commit exists in master"""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_id}"
    )
    return response.is_success and response.json().get("commit") is not None


async def process_issue_events(
    client: httpx.AsyncClient, owner: str, repo: str, issue: Dict
) -> Optional[Dict]:
    """Process events for a single issue"""
    events_response = await client.get(f"{issue['url']}/events")
    if not events_response.is_success:
        return None

    for event in events_response.json():
        if event["event"] == "closed" and event.get("commit_id"):
            if await verify_commit_in_master(client, owner, repo, event["commit_id"]):
                return {
                    "title": issue["title"],
                    "number": issue["number"],
                    "url": issue["html_url"],
                }
    return None


async def get_closed_issues(
    client: httpx.AsyncClient, owner: str, repo: str, since: str
) -> List[Dict]:
    """Get issues closed by commits to master since the given date"""
    response = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        params={
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "since": since,
            "per_page": 100,
        },
    )
    response.raise_for_status()

    tasks = []
    since_date = datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ")

    for issue in response.json():
        if "pull_request" in issue:
            continue

        closed_at = datetime.strptime(issue["closed_at"], "%Y-%m-%dT%H:%M:%SZ")
        if closed_at <= since_date:
            continue

        tasks.append(process_issue_events(client, owner, repo, issue))

    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def process_pull_request(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr: Dict,
    closed_issues: List[Dict],
) -> Optional[str]:
    """Process a single pull request"""
    issue_number = extract_issue_number(pr.get("body"))
    if issue_number:
        issue = await get_issue_details(client, owner, repo, issue_number)
        if issue:
            if not any(i["number"] == issue["number"] for i in closed_issues):
                return TEMPLATE.format(**issue)
            return None

    return TEMPLATE.format(title=pr["title"], number=pr["number"], url=pr["html_url"])


async def get_changes_since_last_release(
    owner: str, repo: str, token: Optional[str] = None
) -> List[str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        print(
            "Warning: No token provided. API rate limiting may occur.", file=sys.stderr
        )

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        # Get the date of last minor release
        since = await get_last_minor_release(client, owner, repo)
        if not since:
            return []

        changes = []

        # Get issues closed by commits to master
        closed_issues = await get_closed_issues(client, owner, repo, since)
        changes.extend([TEMPLATE.format(**issue) for issue in closed_issues])

        # Get merged PRs
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            params={
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
            },
        )
        response.raise_for_status()

        # Process PRs in parallel
        pr_tasks = []
        for pr in response.json():
            if not pr["merged_at"]:
                continue
            if since and pr["merged_at"] <= since:
                break

            pr_tasks.append(
                process_pull_request(client, owner, repo, pr, closed_issues)
            )

        pr_results = await asyncio.gather(*pr_tasks)
        changes.extend([r for r in pr_results if r is not None])

        return changes


async def main_async():
    parser = argparse.ArgumentParser(description="Generate release notes from GitHub")
    parser.add_argument("--token", "-t", help="the file path to the GitHub API token")
    args = parser.parse_args()

    token = None
    if args.token:
        with open(args.token) as f:
            token = f.read().strip()
    try:
        url_path = REPOSITORY.rstrip("/").split("github.com/")[1]
        owner, repo = url_path.split("/")[-2:]
    except (ValueError, IndexError):
        print("Error: Invalid GitHub URL", file=sys.stderr)
        sys.exit(1)

    try:
        notes = await get_changes_since_last_release(owner, repo, token)
        print("\n".join(notes))
    except httpx.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
