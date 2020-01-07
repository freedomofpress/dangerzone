import sys
import os
import inspect
import tempfile


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout the app
    """

    def __init__(self):
        # Temporary directory to store pixel data
        self.tmpdir = tempfile.TemporaryDirectory()
        print(f"tmpdir is: {self.tmpdir.name}")

    def get_resource_path(self, filename):
        if getattr(sys, "dangerzone_dev", False):
            # Look for resources directory relative to python file
            prefix = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(inspect.getfile(inspect.currentframe()))
                    )
                ),
                "share",
            )
        else:
            print("Error, can only run in dev mode so far")

        resource_path = os.path.join(prefix, filename)
        return resource_path
