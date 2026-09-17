# dangerzone-machine

`dangerzone-machine` manages the Podman machine that Dangerzone uses on macOS and Windows. A Podman machine is a small Linux virtual machine in which the sandbox containers run. Dangerzone creates and starts its own machine automatically, so this tool is mostly useful for troubleshooting or resetting a broken installation.

On Linux, Podman runs natively and no virtual machine is involved.

## Location

| Platform | Command |
| -------- | ------- |
| macOS | `/Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine` |
| Windows | `C:\Program Files\Dangerzone\dangerzone-machine.exe` |
| Source tree | `poetry run dangerzone-machine` |

## Usage

The output below is generated from the code at the time the documentation was built, so it matches the installed version of the same release.

<!-- [[[cog
import subprocess
help_text = subprocess.run(["dangerzone-machine", "--help"], capture_output=True, text=True, check=True).stdout.rstrip()
cog.out(f"""```console
{help_text}
```""")
]]] -->
```console
Usage: dangerzone-machine [OPTIONS] COMMAND [ARGS]...

  Manage Dangerzone Podman machines.

Options:
  --log-level [debug|info|warning|error|critical]
                                  Set the logging level.
  --help                          Show this message and exit.

Commands:
  init    Initialize a Dangerzone Podman machine.
  list    List Dangerzone Podman machines.
  raw     Run a raw Podman command.
  remove  Remove the Dangerzone Podman machine.
  reset   Reset all Podman machines.
  start   Start the Dangerzone Podman machine.
  stop    Stop the Dangerzone Podman machine.
```
<!-- [[[end]]] -->

## Commands

<!-- [[[cog
commands = subprocess.run(["dangerzone-machine", "--help"], capture_output=True, text=True, check=True).stdout
for name in [line.split()[0] for line in commands.rpartition("Commands:")[2].splitlines() if line.strip()]:
    help_text = subprocess.run(["dangerzone-machine", name, "--help"], capture_output=True, text=True, check=True).stdout.rstrip()
    cog.out(f"""### `{name}`

```console
{help_text}
```

""")
]]] -->
### `init`

```console
Usage: dangerzone-machine init [OPTIONS]

  Initialize a Dangerzone Podman machine.

Options:
  --cpus INTEGER    Number of CPUs to allocate.
  --memory INTEGER  Amount of memory in bytes.
  --timezone TEXT   Timezone for the machine.
  --help            Show this message and exit.
```

### `list`

```console
Usage: dangerzone-machine list [OPTIONS]

  List Dangerzone Podman machines.

Options:
  --help  Show this message and exit.
```

### `raw`

```console
Usage: dangerzone-machine raw [OPTIONS]

  Run a raw Podman command.

Options:
  --help  Show this message and exit.
```

### `remove`

```console
Usage: dangerzone-machine remove [OPTIONS]

  Remove the Dangerzone Podman machine.

Options:
  -f, --force  Force removal without prompt.
  --help       Show this message and exit.
```

### `reset`

```console
Usage: dangerzone-machine reset [OPTIONS]

  Reset all Podman machines.

Options:
  -f, --force  Force reset without prompt.
  --help       Show this message and exit.
```

### `start`

```console
Usage: dangerzone-machine start [OPTIONS]

  Start the Dangerzone Podman machine.

Options:
  --help  Show this message and exit.
```

### `stop`

```console
Usage: dangerzone-machine stop [OPTIONS]

  Stop the Dangerzone Podman machine.

Options:
  --help  Show this message and exit.
```

<!-- [[[end]]] -->

Notes on individual commands:

* `init`, `start`, and `stop` require the Windows Subsystem for Linux on Windows. Use `stop` after running `dangerzone-cli --linger`.
* `reset` runs `podman machine reset`. This is a destructive action: it removes every Podman machine on the system, including the Dangerzone one and the sandbox image stored in it, so Dangerzone installs both again on next start.
* `raw` runs a Podman command with the Podman binary and connection that Dangerzone uses. Everything after `raw` is passed to Podman untouched.

## Exit status

`0` on success. On a Podman error, the tool prints a ❌ line and aborts with a non-zero status. Declining a confirmation prompt also aborts.

## Examples

Check whether the machine is running:

```console
$ dangerzone-machine list
Name: dz-internal-0.11.0, Status: Running
```

Inspect the sandbox images known to the machine:

```console
$ dangerzone-machine raw images ghcr.io/freedomofpress/dangerzone/v1
```

Start over from a clean state:

```console
$ dangerzone-machine reset
Are you sure you want to reset all Podman machines? This is a destructive action. [y/N]: y
Podman machines reset.
```
