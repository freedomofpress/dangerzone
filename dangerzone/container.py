import click
import platform
import subprocess
import sys
import pipes
import shutil

# What is the container runtime for this platform?
if platform.system() == "Darwin":
    container_runtime = "/usr/local/bin/docker"
elif platform.system() == "Windows":
    container_runtime = shutil.which("docker.exe")
else:
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

    with subprocess.Popen(
        args,
        stdin=None,
        stdout=sys.stdout,
        stderr=sys.stderr,
        bufsize=1,
        universal_newlines=True,
        startupinfo=startupinfo,
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
@click.option("--container-name", default="flmcode/dangerzone")
def ls(container_name):
    """docker image ls [container_name]"""
    sys.exit(exec_container(["image", "ls", container_name]))


@container_main.command()
def pull():
    """docker pull flmcode/dangerzone"""
    sys.exit(exec_container(["pull", "flmcode/dangerzone"]))


@container_main.command()
@click.option("--document-filename", required=True)
@click.option("--pixel-dir", required=True)
@click.option("--container-name", default="flmcode/dangerzone")
def documenttopixels(document_filename, pixel_dir, container_name):
    """docker run --network none -v [document_filename]:/tmp/input_file -v [pixel_dir]:/dangerzone [container_name] document-to-pixels"""
    sys.exit(
        exec_container(
            [
                "run",
                "--network",
                "none",
                "--security-opt=no-new-privileges:true",
                "-v",
                f"{document_filename}:/tmp/input_file",
                "-v",
                f"{pixel_dir}:/dangerzone",
                container_name,
                "document-to-pixels",
            ]
        )
    )


@container_main.command()
@click.option("--pixel-dir", required=True)
@click.option("--safe-dir", required=True)
@click.option("--container-name", default="flmcode/dangerzone")
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
