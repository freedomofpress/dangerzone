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


def exec(args, stdout_callback=None):
    with subprocess.Popen(
        args,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        startupinfo=startupinfo,
    ) as p:
        if stdout_callback:
            for line in p.stdout:
                stdout_callback(line)

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


def host_exec(args, stdout_callback=None):
    args_str = " ".join(pipes.quote(s) for s in args)
    print("> " + args_str)

    return exec(args, stdout_callback)


def vm_exec(args, vm_info, stdout_callback=None):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("--vm-info-path required on this platform")
        return

    args_str = " ".join(pipes.quote(s) for s in args)
    print("VM > " + args_str)

    args = vm_ssh_args(vm_info) + args
    return exec(args, stdout_callback)


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


def exec_container(args, vm_info=None, stdout_callback=None):
    if container_tech == "dangerzone-vm" and vm_info is None:
        print("Invalid VM info")
        return

    if container_tech == "dangerzone-vm":
        args = ["/usr/bin/podman"] + args
        return vm_exec(args, vm_info, stdout_callback)
    else:
        if container_tech == "podman":
            container_runtime = shutil.which("podman")
        else:
            container_runtime = shutil.which("docker")

        args = [container_runtime] + args
        return host_exec(args, stdout_callback)


def load_vm_info(vm_info_path):
    if not vm_info_path:
        return None

    with open(vm_info_path) as f:
        return json.loads(f.read())


def convert(global_common, input_filename, output_filename, ocr_lang, stdout_callback):
    success = False

    container_name = "dangerzone.rocks/dangerzone"
    if ocr_lang:
        ocr = "1"
    else:
        ocr = "0"

    if global_common.vm:
        vm_info = load_vm_info(global_common.vm.vm_info_path)
    else:
        vm_info = None

    # If we're using the VM, create temp dirs in the guest and upload the input file
    # Otherwise, create temp dirs
    if vm_info:
        ssh_args_str = " ".join(pipes.quote(s) for s in vm_ssh_args(vm_info))
        print("If you want to SSH to the VM: " + ssh_args_str)

        guest_tmpdir = vm_mkdir(vm_info)
        input_dir = os.path.join(guest_tmpdir, "input")
        pixel_dir = os.path.join(guest_tmpdir, "pixel")
        safe_dir = os.path.join(guest_tmpdir, "safe")

        guest_input_filename = os.path.join(input_dir, "input_file")
        container_output_filename = os.path.join(safe_dir, "safe-output-compressed.pdf")

        vm_upload(input_filename, guest_input_filename, vm_info)
        input_filename = guest_input_filename
    else:
        tmpdir = tempfile.TemporaryDirectory()
        pixel_dir = os.path.join(tmpdir.name, "pixels")
        safe_dir = os.path.join(tmpdir.name, "safe")
        os.makedirs(pixel_dir, exist_ok=True)
        os.makedirs(safe_dir, exist_ok=True)

        container_output_filename = os.path.join(safe_dir, "safe-output-compressed.pdf")

    # Convert document to pixels
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
    ret = exec_container(args, vm_info, stdout_callback)
    if ret != 0:
        print("documents-to-pixels failed")
    else:
        # TODO: validate convert to pixels output

        # Convert pixels to safe PDF
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
        ret = exec_container(args, vm_info, stdout_callback)
        if ret != 0:
            print("pixels-to-pdf failed")
        else:
            # Move the final file to the right place
            if vm_info:
                vm_download(container_output_filename, output_filename, vm_info)
            else:
                os.rename(container_output_filename, output_filename)

            # We did it
            success = True

    # Clean up
    if vm_info:
        vm_rmdir(guest_tmpdir, vm_info)
    else:
        shutil.rmtree(tmpdir.name)

    return success


# From global_common:

# def validate_convert_to_pixel_output(self, common, output):
#     """
#     Take the output from the convert to pixels tasks and validate it. Returns
#     a tuple like: (success (boolean), error_message (str))
#     """
#     max_image_width = 10000
#     max_image_height = 10000

#     # Did we hit an error?
#     for line in output.split("\n"):
#         if (
#             "failed:" in line
#             or "The document format is not supported" in line
#             or "Error" in line
#         ):
#             return False, output

#     # How many pages was that?
#     num_pages = None
#     for line in output.split("\n"):
#         if line.startswith("Document has "):
#             num_pages = line.split(" ")[2]
#             break
#     if not num_pages or not num_pages.isdigit() or int(num_pages) <= 0:
#         return False, "Invalid number of pages returned"
#     num_pages = int(num_pages)

#     # Make sure we have the files we expect
#     expected_filenames = []
#     for i in range(1, num_pages + 1):
#         expected_filenames += [
#             f"page-{i}.rgb",
#             f"page-{i}.width",
#             f"page-{i}.height",
#         ]
#     expected_filenames.sort()
#     actual_filenames = os.listdir(common.pixel_dir.name)
#     actual_filenames.sort()

#     if expected_filenames != actual_filenames:
#         return (
#             False,
#             f"We expected these files:\n{expected_filenames}\n\nBut we got these files:\n{actual_filenames}",
#         )

#     # Make sure the files are the correct sizes
#     for i in range(1, num_pages + 1):
#         with open(f"{common.pixel_dir.name}/page-{i}.width") as f:
#             w_str = f.read().strip()
#         with open(f"{common.pixel_dir.name}/page-{i}.height") as f:
#             h_str = f.read().strip()
#         w = int(w_str)
#         h = int(h_str)
#         if (
#             not w_str.isdigit()
#             or not h_str.isdigit()
#             or w <= 0
#             or w > max_image_width
#             or h <= 0
#             or h > max_image_height
#         ):
#             return False, f"Page {i} has invalid geometry"

#         # Make sure the RGB file is the correct size
#         if os.path.getsize(f"{common.pixel_dir.name}/page-{i}.rgb") != w * h * 3:
#             return False, f"Page {i} has an invalid RGB file size"

#     return True, True
