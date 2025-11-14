import ctypes
import logging
import shlex
from ctypes import wintypes
from typing import List, Optional, Tuple

from .. import errors

log = logging.getLogger(__name__)


SEE_MASK_NOCLOSEPROCESS = 0x00000040
TIMEOUT_INFINITE = 0xFFFFFFFF


class SHELLEXECUTEINFOW(ctypes.Structure):
    # See https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-shellexecuteinfow
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
    timeout_ms: int = TIMEOUT_INFINITE,
) -> int:
    """Executes a command using the Windows ShellExecuteEx API.

    This allows for features like running executables with privilege elevation (if
    the 'runas' verb is used).

    It waits for the command to complete and returns its exit code.

    Args:
        file: The file to execute.
        params: The parameters to pass to the executable.
        verb: The verb to use for the execution (e.g., 'open', 'runas').
        cwd: The working directory for the new process.
        show: The show command for the new process's window.
        timeout_ms: The timeout in milliseconds to wait for the process to finish.

    Returns:
        The exit code of the process.

    Raises:
        errors.WinShellExecStartFailure: If ShellExecuteExW fails.
        errors.WinShellExecNoHandle: If the process handle is not returned.
        errors.WinShellExecTimeoutExpired: If the process does not finish within the timeout.

    Further reading:
    - https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecuteexw
    """
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
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x00000102
    res = windll.kernel32.WaitForSingleObject(sei.hProcess, timeout_ms)
    if res == WAIT_TIMEOUT:
        raise errors.WinShellExecTimeoutExpired
    exit_code = wintypes.DWORD()
    windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))

    return exit_code.value


def run(cmd: List, check: bool = False) -> int:
    """Convenience wrapper around ShellExecuteEx.

    This function simulates the subprocess.run API, and currently supports passing a
    command as a list, and optionally checking the result.
    """
    prog = cmd[0]
    if len(cmd) > 1:
        args = shlex.join(cmd[1:])
    else:
        args = None

    win_ret = _shellexec(cmd[0], args)

    ret = ctypes.c_int32(win_ret).value
    if check and ret != 0:
        raise errors.WinShellExecProcessError(
            f"Command '{cmd}' failed with exit code: {ret}"
        )
    return ret
