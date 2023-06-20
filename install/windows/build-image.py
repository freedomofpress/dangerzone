import gzip
import os
import subprocess


def main():
    print("Building container image")
    subprocess.run(
        [
            "docker",
            "build",
            "dangerzone/",
            "-f",
            "Dockerfile",
            "--tag",
            "dangerzone.rocks/dangerzone:latest",
        ]
    )

    print("Saving container image")
    cmd = subprocess.Popen(
        [
            "docker",
            "save",
            "dangerzone.rocks/dangerzone:latest",
        ],
        stdout=subprocess.PIPE,
    )

    print("Compressing container image")
    chunk_size = 4 << 12
    with gzip.open("share/container.tar.gz", "wb") as gzip_f:
        while True:
            chunk = cmd.stdout.read(chunk_size)
            if len(chunk) > 0:
                gzip_f.write(chunk)
            else:
                break

    cmd.wait(5)

    print("Looking up the image id")
    image_id = subprocess.check_output(
        [
            "docker",
            "image",
            "list",
            "--format",
            "{{.ID}}",
            "dangerzone.rocks/dangerzone:latest",
        ],
        text=True,
    )
    with open("share/image-id.txt", "w") as f:
        f.write(image_id)


if __name__ == "__main__":
    main()
