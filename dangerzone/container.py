import platform
import subprocess
import pipes
import shutil
import os
import tempfile
import appdirs

# What container tech is used for this platform?
if platform.system() == "Linux":
    container_tech = "podman"
else:
    # Windows, Darwin, and unknown use docker for now, dangerzone-vm eventually
    container_tech = "docker"

# Define startupinfo for subprocesses
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    startupinfo = None


# Name of the dangerzone container
container_name = "dangerzone.rocks/dangerzone"


def exec(args, stdout_callback=None):
    args_str = " ".join(pipes.quote(s) for s in args)
    print("> " + args_str)

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


def exec_container(args, stdout_callback=None):
    if container_tech == "podman":
        container_runtime = shutil.which("podman")
    else:
        container_runtime = shutil.which("docker")

    args = [container_runtime] + args
    return exec(args, stdout_callback)


def convert(input_filename, output_filename, ocr_lang, stdout_callback):
    success = False

    if ocr_lang:
        ocr = "1"
    else:
        ocr = "0"

    dz_tmp = os.path.join(appdirs.user_config_dir("dangerzone"), "tmp")
    os.makedirs(dz_tmp, exist_ok=True)

    tmpdir = tempfile.TemporaryDirectory(dir=dz_tmp)
    pixel_dir = os.path.join(tmpdir.name, "pixels")
    safe_dir = os.path.join(tmpdir.name, "safe")
    os.makedirs(pixel_dir, exist_ok=True)
    os.makedirs(safe_dir, exist_ok=True)

    if container_tech == "docker":
        platform_args = ["--platform", "linux/amd64"]
    else:
        platform_args = []

    # Convert document to pixels
    args = (
        ["run", "--network", "none"]
        + platform_args
        + [
            "-v",
            f"{input_filename}:/tmp/input_file",
            "-v",
            f"{pixel_dir}:/dangerzone",
            container_name,
            "/usr/bin/python3",
            "/usr/local/bin/dangerzone.py",
            "document-to-pixels",
        ]
    )
    ret = exec_container(args, stdout_callback)
    if ret != 0:
        print("documents-to-pixels failed")
    else:
        # TODO: validate convert to pixels output

        # Convert pixels to safe PDF
        args = (
            ["run", "--network", "none"]
            + platform_args
            + [
                "-v",
                f"{pixel_dir}:/dangerzone",
                "-v",
                f"{safe_dir}:/safezone",
                "-e",
                f"OCR={ocr}",
                "-e",
                f"OCR_LANGUAGE={ocr_lang}",
                container_name,
                "/usr/bin/python3",
                "/usr/local/bin/dangerzone.py",
                "pixels-to-pdf",
            ]
        )
        ret = exec_container(args, stdout_callback)
        if ret != 0:
            print("pixels-to-pdf failed")
        else:
            # Move the final file to the right place
            if os.path.exists(output_filename):
                os.remove(output_filename)

            container_output_filename = os.path.join(
                safe_dir, "safe-output-compressed.pdf"
            )
            shutil.move(container_output_filename, output_filename)

            # We did it
            success = True

    # Clean up
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
