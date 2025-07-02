# Podman Desktop support

Starting with Dangerzone 0.9.0, it is possible to use Podman Desktop on
Windows and macOS. The support for this container runtime is currently only
experimental. If you try it out and encounter issues, please reach to us, we'll
be glad to help.

With [Podman Desktop](https://podman-desktop.io/) installed on your machine,
here are the required steps to change the dangerzone container runtime.

First, you need to start Podman, and make sure that it's running. Then, you will
be required to open a terminal and follow these steps:

Ensure that Podman runs in
[rootless](https://github.com/containers/podman/blob/main/docs/tutorials/podman-for-windows.md#rootful--rootless)
mode.

```bash
podman machine inspect --format '{{.Rootful}}'
false
```

## On macOS

To set the container runtime to podman, use this command:

```bash
/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime podman
```

To revert back to the default behavior, pass the `default` value:

```bash
/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime default
```

## On Windows

To set the container runtime to podman, use this command:

```bash
'C:\Program Files\Dangerzone\dangerzone-cli.exe' --set-container-runtime podman
```

To revert back to the default behavior, pass the `default` value:

```bash
'C:\Program Files\Dangerzone\dangerzone-cli.exe' --set-container-runtime podman
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
