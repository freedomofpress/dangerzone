# Using Podman Desktop

Dangerzone uses the system-installed Podman on Linux, and embeds Podman on Windows on macOS.

If you wish to use a Podman Desktop with a specific configuration, follow these steps. These instructions might work for other custom runtimes, but bear in mind that only Podman is currently supported.

## On macOS

To set the container runtime to Podman Desktop, use this command:

```bash
/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime /opt/podman/bin/podman
```

To revert back to the default behavior, pass the `default` value:

```bash
/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime default
```

## On Windows

To set the container runtime to Podman desktop, use this command:

```bash
C:\"Program Files"\Dangerzone\dangerzone-cli.exe --set-container-runtime \path\to\your\runtime
```

To revert back to the default behavior, pass the `default` value:

```bash
C:\"Program Files"\Dangerzone\dangerzone-cli.exe --set-container-runtime podman
```

## FAQ

### I've encountered the following error: `Error: nomap is only supported in rootless mode`

This means that Podman does not run in rootless mode. You can switch to rootless
mode with these steps:

```
podman machine stop
podman machine set --rootful=false
podman machine start
```
