import subprocess
import gzip
import os


def main():
    print("Building dangerzone-converter image")
    subprocess.run(
        [
            "docker",
            "build",
            "dangerzone-converter",
            "--tag",
            "dangerzone.rocks/dangerzone",
        ]
    )

    print("Saving dangerzone-converter image")
    subprocess.run(
        [
            "docker",
            "save",
            "dangerzone.rocks/dangerzone",
            "-o",
            "share/dangerzone-converter.tar",
        ]
    )

    print("Compressing dangerzone-converter image")
    chunk_size = 1024
    with open("share/dangerzone-converter.tar", "rb") as f:
        with gzip.open("share/dangerzone-converter.tar.gz", "wb") as gzip_f:
            while True:
                chunk = f.read(chunk_size)
                if len(chunk) > 0:
                    gzip_f.write(chunk)
                else:
                    break

    os.remove("share/dangerzone-converter.tar")

    print("Looking up the image id")
    image_id = subprocess.check_output(
        [
            "docker",
            "image",
            "list",
            "--format",
            "{{.ID}}",
            "dangerzone.rocks/dangerzone",
        ],
        text=True,
    )
    with open("share/image-id.txt", "w") as f:
        f.write(image_id)


if __name__ == "__main__":
    main()
