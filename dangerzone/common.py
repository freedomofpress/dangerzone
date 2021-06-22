import os
import stat
import platform
import tempfile
import appdirs


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout an open dangerzone window
    """

    def __init__(self):
        # Temporary directory to store pixel data and safe PDFs
        cache_dir = appdirs.user_cache_dir("dangerzone")
        os.makedirs(cache_dir, exist_ok=True)
        self.pixel_dir = tempfile.TemporaryDirectory(
            prefix=os.path.join(cache_dir, "pixel-")
        )
        self.safe_dir = tempfile.TemporaryDirectory(
            prefix=os.path.join(cache_dir, "safe-")
        )

        try:
            # Make the folders world-readable to ensure that the container has permission
            # to access it even if it's owned by root or someone else
            permissions = (
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH
            )
            os.chmod(self.pixel_dir.name, permissions)
            os.chmod(self.safe_dir.name, permissions)
        except:
            pass

        # Name of input and out files
        self.document_filename = None
        self.save_filename = None
