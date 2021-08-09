import os
import sys
import inspect
import requests
import hashlib
import zipfile
import shutil


def main():
    zip_url = "https://github.com/PowerShell/Win32-OpenSSH/releases/download/V8.6.0.0p1-Beta/OpenSSH-Win32.zip"
    expected_zip_sha256 = (
        "0221324212413a6caf260f95e308d22f8c141fc37727b622a6ad50998c46d226"
    )

    # Figure out the paths
    root_path = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        )
    )
    zip_path = os.path.join(root_path, "build", "OpenSSH-Win32.zip")
    extracted_path = os.path.join(root_path, "build", "OpenSSH-Win32")
    bin_path = os.path.join(root_path, "share", "bin")

    os.makedirs(os.path.join(root_path, "build"), exist_ok=True)
    os.makedirs(os.path.join(bin_path), exist_ok=True)

    # Make sure openssh is downloaded
    if not os.path.exists(zip_path):
        print(f"Downloading {zip_url}")
        r = requests.get(zip_url)
        open(zip_path, "wb").write(r.content)
        zip_sha256 = hashlib.sha256(r.content).hexdigest()
    else:
        zip_data = open(zip_path, "rb").read()
        zip_sha256 = hashlib.sha256(zip_data).hexdigest()

    # Compare the hash
    if zip_sha256 != expected_zip_sha256:
        print("ERROR! The sha256 doesn't match:")
        print("expected: {}".format(expected_zip_sha256))
        print("  actual: {}".format(zip_sha256))
        sys.exit(-1)

    # Extract the zip
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(os.path.join(root_path, "build"))

    # Copy binaries to share
    shutil.copy(os.path.join(extracted_path, "libcrypto.dll"), bin_path)
    shutil.copy(os.path.join(extracted_path, "moduli"), bin_path)
    shutil.copy(os.path.join(extracted_path, "scp.exe"), bin_path)
    shutil.copy(os.path.join(extracted_path, "ssh-agent.exe"), bin_path)
    shutil.copy(os.path.join(extracted_path, "ssh-keygen.exe"), bin_path)
    shutil.copy(os.path.join(extracted_path, "ssh.exe"), bin_path)
    shutil.copy(os.path.join(extracted_path, "sshd.exe"), bin_path)
    shutil.copyfile(
        os.path.join(extracted_path, "LICENSE.txt"),
        os.path.join(bin_path, "LICENSE-OpenSSH.txt"),
    )


if __name__ == "__main__":
    main()
