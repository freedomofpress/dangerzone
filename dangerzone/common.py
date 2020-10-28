import os
import platform
import tempfile


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout an open dangerzone window
    """

    def __init__(self):
        # Temporary directory to store pixel data and safe PDFs
        if platform.system() == "Windows":
            self.pixel_dir = tempfile.TemporaryDirectory(prefix="dangerzone-pixel-")
            self.safe_dir = tempfile.TemporaryDirectory(prefix="dangerzone-safe-")
        elif platform.system() == "Darwin":
            # In macOS, temp dirs must be in /tmp (or a few other paths) for Docker to mount them
            self.pixel_dir = tempfile.TemporaryDirectory(
                prefix="/tmp/dangerzone-pixel-"
            )
            self.safe_dir = tempfile.TemporaryDirectory(prefix="/tmp/dangerzone-safe-")
        else:
            # In Linux, temp dirs must be in the homedir for the snap package version of Docker to mount them
            cache_dir = os.path.expanduser("~/.cache/dangerzone")
            os.makedirs(cache_dir, exist_ok=True)
            self.pixel_dir = tempfile.TemporaryDirectory(
                prefix=os.path.join(cache_dir, "pixel-")
            )
            self.safe_dir = tempfile.TemporaryDirectory(
                prefix=os.path.join(cache_dir, "safe-")
            )

        print(
            f"Temporary directories created, dangerous={self.pixel_dir.name}, safe={self.safe_dir.name}"
        )

        # Name of input and out files
        self.document_filename = None
        self.save_filename = None
