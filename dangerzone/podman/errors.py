import subprocess


class PodmanCommandError(Exception):
    def __init__(self, error: subprocess.CalledProcessError) -> None:
        self.error = error
        msg = f"The Podman process failed with the following error: {error}"
        super().__init__(msg)
