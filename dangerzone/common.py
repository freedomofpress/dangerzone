import platform
import tempfile


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout an open dangerzone window
    """

    def __init__(self):
        # Temporary directory to store pixel data
        # Note in macOS, temp dirs must be in /tmp (or a few other paths) for Docker to mount them
        if platform.system() == "Windows":
            self.pixel_dir = tempfile.TemporaryDirectory(prefix="dangerzone-pixel-")
            self.safe_dir = tempfile.TemporaryDirectory(prefix="dangerzone-safe-")
        else:
            self.pixel_dir = tempfile.TemporaryDirectory(
                prefix="/tmp/dangerzone-pixel-"
            )
            self.safe_dir = tempfile.TemporaryDirectory(prefix="/tmp/dangerzone-safe-")
        print(
            f"Temporary directories created, dangerous={self.pixel_dir.name}, safe={self.safe_dir.name}"
        )

        # Name of input and out files
        self.document_filename = None
        self.save_filename = None
