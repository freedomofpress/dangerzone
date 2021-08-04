#!/usr/bin/env python3
import os
import subprocess
import shutil
import json


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("Creating dangerzone image")
    subprocess.run(
        [
            "podman",
            "build",
            "--pull-always",
            "--tag",
            "dangerzone.rocks/dangerzone",
            ".",
        ],
        cwd=os.path.join(root, "dangerzone-converter"),
    )

    print("Cleaning up from last time")
    container_dir = os.path.join(root, "share", "container")
    shutil.rmtree(container_dir, ignore_errors=True)
    os.makedirs(container_dir, exist_ok=True)

    print("Saving image ID")
    image_id = None
    images = json.loads(
        subprocess.check_output(["podman", "image", "list", "--format", "json"])
    )
    for image in images:
        if "dangerzone.rocks/dangerzone:latest" in image["Names"]:
            image_id = image["Id"]
            break

    if not image_id:
        print("Could not find image, aborting")
        return

    with open(os.path.join(container_dir, "image_id.txt"), "w") as f:
        f.write(f"{image_id}")

    print("Saving image")
    subprocess.run(
        [
            "podman",
            "save",
            "-o",
            os.path.join(container_dir, "dangerzone.tar"),
            "dangerzone.rocks/dangerzone",
        ]
    )

    print("Compressing image")
    subprocess.run(["gzip", "dangerzone.tar"], cwd=container_dir)


if __name__ == "__main__":
    main()
