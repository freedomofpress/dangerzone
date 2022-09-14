import pathlib
import platform
import sys


def get_resource_path(filename: str) -> str:
    if getattr(sys, "dangerzone_dev", False):
        # Look for resources directory relative to python file
        project_root = pathlib.Path(__file__).parent.parent
        prefix = project_root.joinpath("share")
    else:
        if platform.system() == "Darwin":
            bin_path = pathlib.Path(sys.executable)
            app_path = bin_path.parent.parent
            prefix = app_path.joinpath("Resources", "share")
        elif platform.system() == "Linux":
            prefix = pathlib.Path(sys.prefix).joinpath("share", "dangerzone")
        elif platform.system() == "Windows":
            exe_path = pathlib.Path(sys.executable)
            dz_install_path = exe_path.parent
            prefix = dz_install_path.joinpath("share")
        else:
            raise NotImplementedError(f"Unsupported system {platform.system()}")
    resource_path = prefix.joinpath(filename)
    return str(resource_path)
