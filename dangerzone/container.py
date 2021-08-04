import click
import platform
import subprocess
import sys
import pipes
import shutil
import json
import os
import uuid
import tempfile

# What container tech is used for this platform?
if platform.system() == "Darwin":
    container_tech = "dangerzone-vm"
elif platform.system() == "Linux":
    container_tech = "podman"
else:
    # Windows and unknown use docker for now, dangerzone-vm eventually
    container_tech = "docker"

# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    startupinfo = None


def exec(args):
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


def vm_ssh_args(vm_info):
    return [
        "/usr/bin/ssh",
        "-q",
        "-i",
        vm_info["client_key_path"],
        "-p",
        str(vm_info["tunnel_port"]),
        "-o",
        "StrictHostKeyChecking=no",
        "user@127.0.0.1",
    ]


def vm_scp_args(vm_info):
    return [
        "/usr/bin/scp",
        "-i",
        vm_info["client_key_path"],
        "-P",
        str(vm_info["tunnel_port"]),
        "-o",
        "StrictHostKeyChecking=no",
    ]


def host_exec(args):
    args_str = " ".join(pipes.quote(s) for s in args)
    print("> " + args_str)

    return exec(args)


def vm_exec(args, vm_info):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("--vm-info-path required on this platform")
        return

    args_str = " ".join(pipes.quote(s) for s in args)
    print("VM > " + args_str)

    args = vm_ssh_args(vm_info) + args
    return exec(args)


def vm_mkdir(vm_info):
    guest_path = os.path.join("/home/user/", str(uuid.uuid4()))
    vm_exec(["/bin/mkdir", guest_path], vm_info)
    return guest_path


def vm_rmdir(guest_path, vm_info):
    vm_exec(["/bin/rm", "-r", guest_path], vm_info)


def vm_upload(host_path, guest_path, vm_info):
    args = vm_scp_args(vm_info) + [host_path, f"user@127.0.0.1:{guest_path}"]
    print(f"Uploading '{host_path}' to VM at '{guest_path}'")
    host_exec(args)


def vm_download(guest_path, host_path, vm_info):
    args = vm_scp_args(vm_info) + [f"user@127.0.0.1:{guest_path}", host_path]
    print(f"Downloading '{guest_path}' from VM to '{host_path}'")
    host_exec(args)


def exec_container(args, vm_info=None):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("--vm-info-path required on this platform")
        return

    if container_tech == "dangerzone-vm":
        args = ["/usr/bin/podman"] + args
        return vm_exec(args, vm_info)
    else:
        if container_tech == "podman":
            container_runtime = shutil.which("podman")
        else:
            container_runtime = shutil.which("docker")

        args = [container_runtime] + args
        return host_exec(args)


def load_vm_info(vm_info_path):
    if not vm_info_path:
        return None

    with open(vm_info_path) as f:
        return json.loads(f.read())


@click.group()
def container_main():
    """
    Dangerzone container commands. Humans don't need to run this command by themselves.
    """
    pass


@container_main.command()
@click.option("--vm-info-path", default=None)
def ls(vm_info_path):
    """docker image ls [container_name]"""
    if vm_info_path:
        container_name = "localhost/dangerzone"
    else:
        container_name = "dangerzone"

    sys.exit(
        exec_container(["image", "ls", container_name]), load_vm_info(vm_info_path)
    )


@container_main.command()
@click.option("--vm-info-path", default=None)
@click.option("--input-filename", required=True)
@click.option("--output-filename", required=True)
@click.option("--ocr", required=True)
@click.option("--ocr-lang", required=True)
def convert(vm_info_path, input_filename, output_filename, ocr, ocr_lang):
    container_name = "dangerzone.rocks/dangerzone"
    vm_info = load_vm_info(vm_info_path)

    if vm_info:
        # If there's a VM:
        # - make inputdir on VM
        # - make pixeldir on VM
        # - make safedir on VM
        # - scp input file to inputdir
        # - run podman documenttopixels
        # - run podman pixelstopdf
        # - scp output file to host
        # - delete inputdir, pixeldir, safedir
        ssh_args_str = " ".join(pipes.quote(s) for s in vm_ssh_args(vm_info))
        print("If you want to SSH to the VM: " + ssh_args_str)

        input_dir = vm_mkdir(vm_info)
        pixel_dir = vm_mkdir(vm_info)
        safe_dir = vm_mkdir(vm_info)

        guest_input_filename = os.path.join(input_dir, "input_file")
        guest_output_filename = os.path.join(safe_dir, "safe-output-compressed.pdf")

        vm_upload(input_filename, guest_input_filename, vm_info)

        args = [
            "run",
            "--network",
            "none",
            "-v",
            f"{guest_input_filename}:/tmp/input_file",
            "-v",
            f"{pixel_dir}:/dangerzone",
            container_name,
            "document-to-pixels",
        ]
        ret = exec_container(args, vm_info)
        if ret != 0:
            print("documents-to-pixels failed")
        else:
            args = [
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
            ret = exec_container(args, vm_info)
            if ret != 0:
                print("pixels-to-pdf failed")
            else:
                vm_download(guest_output_filename, output_filename, vm_info)

        vm_rmdir(input_dir, vm_info)
        vm_rmdir(pixel_dir, vm_info)
        vm_rmdir(safe_dir, vm_info)

        sys.exit(ret)

    else:
        # If there's not a VM
        # - make tmp pixeldir
        # - make tmp safedir
        # - run podman documenttopixels
        # - run podman pixelstopdf
        # - copy safe PDF to output filename
        # - delete pixeldir, safedir

        tmpdir = tempfile.TemporaryDirectory()
        pixel_dir = os.path.join(tmpdir.name, "pixels")
        safe_dir = os.path.join(tmpdir.name, "safe")
        os.makedirs(pixel_dir, exist_ok=True)
        os.makedirs(safe_dir, exist_ok=True)

        container_output_filename = os.path.join(safe_dir, "safe-output-compressed.pdf")

        args = [
            "run",
            "--network",
            "none",
            "-v",
            f"{input_filename}:/tmp/input_file",
            "-v",
            f"{pixel_dir}:/dangerzone",
            container_name,
            "document-to-pixels",
        ]
        ret = exec_container(args)
        if ret != 0:
            print("documents-to-pixels failed")
        else:
            args = [
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
            ret = exec_container(args)
            if ret != 0:
                print("pixels-to-pdf failed")
            else:
                os.rename(container_output_filename, output_filename)

        shutil.rmtree(tmpdir.name)
