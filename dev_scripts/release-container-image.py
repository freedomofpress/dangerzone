#!/usr/bin/env python3
"""
Script to automate the release of a new Dangerzone container image.

This script automates the manual steps described in the container image release
process, including:
1. Picking a release candidate image
2. Attesting provenance and reproducibility
3. Signing and publishing the image
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_NAME_PATH = PROJECT_ROOT / "share" / "image-name.txt"
DOCKER_ENV_PATH = PROJECT_ROOT / "Dockerfile.env"


def extract_debian_archive_date(image):
    """We want the "20251007" part out of this:

    ghcr.io/almet/dangerzone/dangerzone:20251007-0.9.0-158-g1603d30
    """
    full_tag = image.split(":")[1]
    return full_tag.split("-")[0]


def validate_commit_format_only(ctx, param, value):
    """Validate only the format, don't check if commit exists."""
    if value is None:
        return value

    if not re.match(r"^[0-9a-f]{40}$", value.lower()):
        raise click.BadParameter(
            f"Invalid commit hash format: {value}. This must be the complete SHA1 commit."
        )

    return value


def run(cmd, check=True, capture_output=False, **kwargs):
    """Run a command and optionally capture output."""
    click.echo(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, check=check, capture_output=capture_output, text=True, **kwargs
    )
    return result


def preflight_check():
    """Check that all required tools are available in PATH."""
    missing_tools = []

    for tool in ["uv", "crane", "git", "poetry"]:
        result = subprocess.run(
            ["which", tool],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            missing_tools.append(tool)

    if missing_tools:
        click.echo(f"\n❌ Missing required tools: {', '.join(missing_tools)}")
        click.echo("Please install them and ensure they are in your PATH.")
        sys.exit(1)


@click.command()
@click.option(
    "--commit",
    default=None,
    help=(
        "The full SHA1 commit to use when attesting, reproducing and signing. "
        "Defaults to the git HEAD of the current branch."
    ),
    callback=validate_commit_format_only,
)
@click.option(
    "--ghcr-signer-path",
    type=click.Path(exists=True),
    required=True,
    help="Path to the ghcr-signer repository",
    default="../ghcr-signer",
)
@click.option(
    "--repository", default="freedomofpress/dangerzone", help="The repository to use"
)
@click.option("--branch", default="main")
@click.option("--workflow", default=".github/workflows/release-container-image.yml")
@click.option("--image-name", default=IMAGE_NAME_PATH.read_text().strip())
@click.option(
    "--skip-reproduction-for",
    help="If the reproduction has already been done, the digests to avoid reproducing can be specified with this option",
    multiple=True,
)
@click.option(
    "--skip-signing", help="Skip the generation of the signatures", is_flag=True
)
def attest_release_sign(
    commit,
    ghcr_signer_path,
    repository,
    branch,
    workflow,
    image_name,
    skip_reproduction_for,
    skip_signing,
):
    """
    Attest the provenance of a commit, reproduce its digest and prepare signatures
    """

    # Check that all required tools are available
    preflight_check()

    # Get commit hash
    if not commit:
        result = run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
        )
        commit = result.stdout.strip()

    root_manifest, debian_archive_date = get_candidate_image(commit, image_name)
    attest_provenance(root_manifest, commit, repository, branch, workflow)
    digests = get_platform_digests(root_manifest)

    # Create temporary directory and clone repository once for all reproductions
    temp_dir = tempfile.mkdtemp(prefix="dangerzone-reproduce-")
    click.echo(f"\n📁 Created temporary directory: {temp_dir}")

    try:
        # Git clone the Dangerzone repository
        click.echo("📥 Cloning Dangerzone repository...")
        run(
            [
                "git",
                "clone",
                f"https://github.com/{repository}.git",
                temp_dir,
            ]
        )
        click.echo("✅ Repository cloned")

        # Checkout the specific commit
        click.echo(f"🔀 Checking out commit {commit}...")
        run(["git", "-C", temp_dir, "checkout", commit])

        for platform in ["linux/amd64", "linux/arm64"]:
            platform_digest = digests[platform]
            if platform_digest in skip_reproduction_for:
                click.echo(
                    f"⏩ Skipping reproduction for platform {platform} (digest {platform_digest})"
                )
            else:
                reproduce_image(
                    root_manifest,
                    platform,
                    debian_archive_date,
                    platform_digest,
                    temp_dir,
                )
    finally:
        # Clean up temporary directory
        click.echo(f"\n🧹 Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)

    if skip_signing:
        click.echo("⏩ Skipping signing")
    else:
        sign_image(root_manifest, ghcr_signer_path)


def attest_provenance(full_image, commit, repository, branch, workflow):
    click.echo(f"\n🔐 Attesting provenance for image: {full_image}")
    click.echo(f"   Commit: {commit}\n")

    try:
        run(
            [
                "poetry",
                "run",
                "python",
                "dev_scripts/dangerzone-image",
                "attest-provenance",
                "--repository",
                repository,
                "--branch",
                branch,
                "--commit",
                commit,
                "--workflow",
                workflow,
                full_image,
            ]
        )
        click.echo("\n✅ Provenance attestation successful\n")
    except subprocess.CalledProcessError as e:
        click.echo(f"\n❌ Provenance attestation failed: {e}\n")
        sys.exit(1)


def get_candidate_image(commit, image_name):
    short_commit = commit[:7]
    click.echo(f"\n📦 Looking for images for commit: {short_commit}")
    click.echo(f"   Repository: {image_name}\n")

    # Get the latest container image with this commit
    try:
        result = run(
            [
                "crane",
                "ls",
                "--full-ref",
                image_name,
            ],
            capture_output=True,
        )

        # Filter images matching the commit
        images = [line for line in result.stdout.splitlines() if short_commit in line]

        if not images:
            click.echo(f"❌ No images found for commit {short_commit}")
            sys.exit(1)

        # Get the fresher one
        latest_image = images[-1]
        debian_date = extract_debian_archive_date(latest_image)

        # Get the digest
        result = run(
            ["crane", "digest", latest_image],
            capture_output=True,
        )
        digest = result.stdout.strip()

        # Format as image@digest
        image_base = latest_image.split(":")[0]
        full_image = f"{image_base}@{digest}"

        click.echo(f"✅ Found image:")
        click.echo(f"   {full_image}\n")
        return full_image, debian_date

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error finding candidate image: {e}")
        sys.exit(1)


def get_platform_digests(full_image):
    """Get platform-specific full_image digests."""
    click.echo(f"\n📋 Getting platform-specific digests for: {full_image}\n")

    try:
        result = run(
            ["crane", "manifest", full_image],
            capture_output=True,
        )
        manifest = json.loads(result.stdout)
        click.echo("✅ Platform digests retrieved:")
        platforms = {
            f"{m['platform']['os']}/{m['platform']['architecture']}": m["digest"]
            for m in manifest["manifests"]
        }
        for architecture, digest in platforms.items():
            click.echo(f"- {architecture}: {digest}")

        if len(platforms) != 2:
            click.echo(
                f"❌ Unsupported number of platforms found: {', '.join(platforms.keys())}"
            )
            sys.exit(1)

        return platforms
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Error getting platform digests: {e}")
        sys.exit(1)


def reproduce_image(
    root_manifest,
    platform,
    debian_archive_date,
    platform_image_digest,
    temp_dir,
):
    """Reproduce the image for a specific platform using the cloned repository."""
    # Format image with digest
    image_base = root_manifest.split("@")[0]
    platform_image = f"{image_base}@{platform_image_digest}"

    click.echo(f"\n🔄 Reproducing image for platform: {platform}")
    click.echo(f"   Root manifest: {root_manifest}")
    click.echo(f"   Platform image digest: {platform_image_digest}")
    click.echo(f"   Debian archive date: {debian_archive_date}")
    click.echo(f"   Platform image: {platform_image}")
    click.echo(f"   Repository path: {temp_dir}\n")

    try:
        # Run the reproduce-image command from the cloned repository
        click.echo("🏗️  Running reproduce-image command...")
        run(
            [
                "poetry",
                "run",
                "python",
                f"{temp_dir}/dev_scripts/reproduce-image.py",
                "--debian-archive-date",
                debian_archive_date,
                "--platform",
                platform,
                platform_image,
            ],
            cwd=temp_dir,
        )
        click.echo(f"\n✅ Image reproduction successful for {platform}\n")

    except subprocess.CalledProcessError as e:
        click.echo(f"\n❌ Image reproduction failed: {e}\n")
        sys.exit(1)


def sign_image(image, ghcr_signer_path):
    """Sign the image and store signatures."""
    click.echo(f"\n✍️  Signing image: {image}")
    click.echo(f"   Using ghcr-signer at: {ghcr_signer_path}\n")

    try:
        # Change to ghcr-signer directory
        ghcr_signer_script = Path(ghcr_signer_path) / "ghcr-signer.py"

        if not ghcr_signer_script.exists():
            click.echo(f"❌ ghcr-signer.py not found at {ghcr_signer_script}")
            sys.exit(1)

        # Run the signing script
        run(
            [
                "uv",
                "run",
                str(ghcr_signer_script),
                "prepare",
                "--sk",
                image,
            ],
            check=True,
        )

        click.echo("\n✅ Image signed successfully")
        click.echo("⚠️  Remember to:")
        click.echo("   1. Create a PR with the signatures")
        click.echo("   2. Wait for CI to pass")
        click.echo("   3. Merge the PR\n")

    except subprocess.CalledProcessError as e:
        click.echo(f"\n❌ Image signing failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    attest_release_sign()
