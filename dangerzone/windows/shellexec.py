import ctypes
import logging
import shlex
from ctypes import wintypes
from typing import List, Optional, Tuple

from .. import errors

log = logging.getLogger(__name__)


SEE_MASK_NOCLOSEPROCESS = 0x00000040


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def _shellexec(
    file: str,
    params: Optional[str] = None,
    verb: str = "open",
    cwd: Optional[str] = None,
    show: int = 1,
    timeout_ms: Optional[int] = None,
) -> int:
    from ctypes import windll  # type: ignore [attr-defined]

    ShellExecuteEx = windll.shell32.ShellExecuteExW
    ShellExecuteEx.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    ShellExecuteEx.restype = wintypes.BOOL

    sei = SHELLEXECUTEINFOW()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.hwnd = None
    sei.lpVerb = verb
    sei.lpFile = file
    sei.lpParameters = params
    sei.lpDirectory = cwd
    sei.nShow = show
    if not ShellExecuteEx(ctypes.byref(sei)):
        raise errors.WinShellExecStartFailure
    if not sei.hProcess:
        raise errors.WinShellExecNoHandle
    INFINITE = 0xFFFFFFFF
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x00000102
    res = windll.kernel32.WaitForSingleObject(sei.hProcess, timeout_ms)
    if res == WAIT_TIMEOUT:
        raise errors.WinShellExecTimeoutExpired
    exit_code = wintypes.DWORD()
    windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))

    return exit_code.value


def run(cmd: List, check: bool = False) -> int:
    prog = cmd[0]
    if len(cmd) > 1:
        args = shlex.join(cmd[1:])
    else:
        args = None

    win_ret = _shellexec(cmd[0], args)

    ret = int(ctypes.c_int32(win_ret))
    if check and ret != 0:
        raise errors.WinShellExecProcessError(
            f"Command '{cmd}' failed with exit code: {ret}"
        )
    return ret


# # Example usage:
# ok, info = run(
#     r"C:\Windows\System32\notepad.exe", params=None, timeout_ms=2000
# )
# print(ok, info)
