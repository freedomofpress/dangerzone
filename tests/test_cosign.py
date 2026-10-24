import os
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from dangerzone.updater import cosign


@pytest.mark.skipif(os.name == "nt", reason="Fixture uses a POSIX executable")
@pytest.mark.parametrize("vendored", [True, False])
def test_cosign_searches_vendor_then_system(
    tmp_path: Path, mocker: MockerFixture, vendored: bool
) -> None:
    vendor = tmp_path / "vendor"
    system = tmp_path / "system"
    vendor.mkdir()
    system.mkdir()
    for directory, label in [(system, "system"), (vendor, "vendor")]:
        if directory == vendor and not vendored:
            continue
        binary = directory / "cosign"
        binary.write_text(f"#!/bin/sh\nprintf '{label}'\n")
        binary.chmod(0o755)

    mocker.patch.object(cosign, "get_resource_path", return_value=vendor)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.dict(os.environ, {"PATH": str(system)})

    result = cosign._cosign_run(["version"])

    assert result.stdout.decode() == ("vendor" if vendored else "system")


def test_cosign_preserves_environment_and_search_path(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    vendor = tmp_path / "vendor"
    mocker.patch.object(cosign, "get_resource_path", return_value=vendor)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.object(cosign.shutil, "which", return_value="cosign")
    run = mocker.patch.object(
        cosign, "subprocess_run", return_value=subprocess.CompletedProcess([], 0)
    )
    mocker.patch.dict(
        os.environ, {"PATH": "system-path", "REGISTRY_AUTH_FILE": "user-auth"}
    )

    cosign._cosign_run(["version"], disable_auth=True)

    environment = run.call_args.kwargs["env"]
    assert environment["PATH"] == str(vendor) + os.pathsep + "system-path"
    assert environment["REGISTRY_AUTH_FILE"] == "user-auth"


def test_cosign_missing_executable_raises(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch.object(cosign, "get_resource_path", return_value=tmp_path)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.dict(os.environ, {"PATH": str(tmp_path)})
    with pytest.raises(FileNotFoundError):
        cosign._cosign_run(["version"])


def test_vendored_cosign_precedes_windows_current_directory(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    vendor = tmp_path / "vendor"
    vendored_binary = str(vendor / "cosign.exe")
    mocker.patch.object(cosign, "get_resource_path", return_value=vendor)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.object(cosign.platform, "system", return_value="Windows")
    # Windows bare-name lookup can search the current directory before PATH.
    which = mocker.patch.object(
        cosign.shutil,
        "which",
        side_effect=lambda command, **kwargs: (
            "untrusted-current-directory/cosign.exe"
            if command in ("cosign", "cosign.exe")
            else vendored_binary
        ),
    )
    run = mocker.patch.object(
        cosign, "subprocess_run", return_value=subprocess.CompletedProcess([], 0)
    )

    cosign._cosign_run(["version"])

    which.assert_called_once_with(str(vendor / "cosign.exe"))
    assert run.call_args.args[0] == [vendored_binary, "version"]


def test_system_cosign_lookup_does_not_implicitly_search_current_directory(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    vendor = tmp_path / "vendor"
    system = tmp_path / "system"
    system_binary = str(system / "cosign.exe")
    mocker.patch.object(cosign.platform, "system", return_value="Windows")
    mocker.patch.object(cosign, "get_resource_path", return_value=vendor)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.dict(os.environ, {"PATH": str(system)})
    which = mocker.patch.object(
        cosign.shutil,
        "which",
        side_effect=lambda command: (
            system_binary if command == str(system / "cosign.exe") else None
        ),
    )
    run = mocker.patch.object(
        cosign, "subprocess_run", return_value=subprocess.CompletedProcess([], 0)
    )

    cosign._cosign_run(["version"])

    assert which.call_args_list == [
        mocker.call(str(vendor / "cosign.exe")),
        mocker.call(str(system / "cosign.exe")),
    ]
    assert run.call_args.args[0] == [system_binary, "version"]


@pytest.mark.skipif(os.name == "nt", reason="Fixture uses a POSIX executable")
def test_windows_binary_name_includes_exe(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    binary = vendor / "cosign.exe"
    binary.write_text("#!/bin/sh\nprintf 'vendored-exe'\n")
    binary.chmod(0o755)
    mocker.patch.object(cosign, "get_resource_path", return_value=vendor)
    mocker.patch.object(cosign, "linux_system_is", return_value=False)
    mocker.patch.object(cosign.platform, "system", return_value="Windows")
    mocker.patch.dict(os.environ, {"PATH": str(tmp_path)})
    # Run the POSIX fixture directly; util.subprocess_run uses Windows startup flags.
    mocker.patch.object(cosign, "subprocess_run", side_effect=subprocess.run)

    assert cosign._cosign_run(["version"]).stdout == b"vendored-exe"
