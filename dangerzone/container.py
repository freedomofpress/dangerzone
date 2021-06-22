import click
import platform
import subprocess
import sys
import pipes
import shutil
import os

# What is the container runtime for this platform?
if platform.system() == "Darwin":
    container_tech = "docker"
    container_runtime = "/usr/local/bin/docker"
elif platform.system() == "Windows":
    container_tech = "docker"
    container_runtime = shutil.which("docker.exe")
elif platform.system() == "Linux":
    container_tech = "podman"
    container_runtime = shutil.which("podman")
else:
    print("Unknown operating system, defaulting to Docker")
    container_tech = "docker"
    container_runtime = shutil.which("docker")

# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    startupinfo = None


def exec_container(args):
    args = [container_runtime] + args

    args_str = " ".join(pipes.quote(s) for s in args)
    print("> " + args_str)
    sys.stdout.flush()

    # In Tails, tell the container runtime to download over Tor
    if (
        platform.system() == "Linux"
        and os.getlogin() == "amnesia"
        and os.getuid() == 1000
    ):
        env = os.environ.copy()
        env["HTTP_PROXY"] = "socks5://127.0.0.1:9050"
    else:
        env = None

    with subprocess.Popen(
        args,
        stdin=None,
        stdout=sys.stdout,
        stderr=sys.stderr,
        bufsize=1,
        universal_newlines=True,
        startupinfo=startupinfo,
        env=env,
    ) as p:
        p.communicate()
        return p.returncode


@click.group()
def container_main():
    """
    Dangerzone container commands with elevated privileges.
    Humans don't need to run this command by themselves.
    """
    pass


@container_main.command()
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
def ls(container_name):
    """docker image ls [container_name]"""
    sys.exit(exec_container(["image", "ls", container_name]))


@container_main.command()
def pull():
    """docker pull flmcode/dangerzone"""
    sys.exit(exec_container(["pull", "docker.io/flmcode/dangerzone"]))


@container_main.command()
@click.option("--document-filename", required=True)
@click.option("--pixel-dir", required=True)
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
def documenttopixels(document_filename, pixel_dir, container_name):
    """docker run --network none -v [document_filename]:/tmp/input_file -v [pixel_dir]:/dangerzone [container_name] document-to-pixels"""
    args = ["run", "--network", "none"]

    # docker uses --security-opt, podman doesn't
    if container_tech == "docker":
        args += ["--security-opt=no-new-privileges:true"]

    args += [
        "-v",
        f"{document_filename}:/tmp/input_file",
        "-v",
        f"{pixel_dir}:/dangerzone",
        container_name,
        "document-to-pixels",
    ]
    sys.exit(exec_container(args))


@container_main.command()
@click.option("--pixel-dir", required=True)
@click.option("--safe-dir", required=True)
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
@click.option("--ocr", required=True)
@click.option("--ocr-lang", required=True)
def pixelstopdf(pixel_dir, safe_dir, container_name, ocr, ocr_lang):
    """docker run --network none -v [pixel_dir]:/dangerzone -v [safe_dir]:/safezone [container_name] -e OCR=[ocr] -e OCR_LANGUAGE=[ocr_lang] pixels-to-pdf"""
    sys.exit(
        exec_container(
            [
                "run",
                "--network",
                "none",
                "-v",
                f"{pixel_dir}:/dangerzone",
                "-v",
                f"{safe_dir}:/safezone",
                "-e",
                f"OCR={ocr}",
                "-e",
                f"OCR_LANGUAGE={ocr_lang}",
                container_name,
                "pixels-to-pdf",
            ]
        )
    )
