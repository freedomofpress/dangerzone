import click
import platform
import subprocess
import sys
import pipes
import shutil
import json

# What is the container runtime for this platform?
if platform.system() == "Darwin":
    container_tech = "dangerzone-vm"
    container_runtime = shutil.which("docker")
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


def exec(args):
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


def exec_vm(args, vm_info):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("--vm-info-path required on this platform")
        return

    args = [
        "/usr/bin/ssh",
        "-q",
        "-i",
        vm_info["client_key_path"],
        "-p",
        vm_info["tunnel_port"],
        "-o",
        "StrictHostKeyChecking=no",
        "user@127.0.0.1",
    ] + args
    return exec(args)


def exec_container(args, vm_info):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("--vm-info-path required on this platform")
        return

    if container_tech == "dangerzone-vm":
        args = ["podman"] + args
        return exec_vm(args, vm_info)

    args = [container_runtime] + args
    return exec(args)


def load_vm_info(vm_info_path):
    if not vm_info_path:
        return None

    with open(vm_info_path) as f:
        return json.loads(f.read())


@click.group()
def container_main():
    """
    Dangerzone container commands with elevated privileges.
    Humans don't need to run this command by themselves.
    """
    pass


@container_main.command()
@click.option("--vm-info-path", default=None)
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
def ls(vm_info_path, container_name):
    """docker image ls [container_name]"""
    sys.exit(
        exec_container(["image", "ls", container_name]), load_vm_info(vm_info_path)
    )


@container_main.command()
@click.option("--vm-info-path", default=None)
@click.option("--document-filename", required=True)
@click.option("--pixel-dir", required=True)
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
def documenttopixels(vm_info_path, document_filename, pixel_dir, container_name):
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
    sys.exit(exec_container(args, load_vm_info(vm_info_path)))


@container_main.command()
@click.option("--vm-info-path", default=None)
@click.option("--pixel-dir", required=True)
@click.option("--safe-dir", required=True)
@click.option("--container-name", default="docker.io/flmcode/dangerzone")
@click.option("--ocr", required=True)
@click.option("--ocr-lang", required=True)
def pixelstopdf(vm_info_path, pixel_dir, safe_dir, container_name, ocr, ocr_lang):
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
            ],
            load_vm_info(vm_info_path),
        )
    )
