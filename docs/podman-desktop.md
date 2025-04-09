# Podman Desktop support

Starting with Dangerzone 0.9.0, it is possible to use Podman Desktop on
Windows and macOS. The support for this container runtime is currently only
experimental. If you try it out and encounter issues, please reach to us, we'll
be glad to help.

With [Podman Desktop](https://podman-desktop.io/) installed on your machine,
here are the required steps to change the dangerzone container runtime.

You will be required to open a terminal and follow these steps:

## On macOS

You will need to configure podman to access the shared Dangerzone resources:

```bash
podman machine stop
podman machine rm
cat > ~/.config/containers/containers.conf <<EOF
[machine]
volumes = ["/Users:/Users", "/private:/private", "/var/folders:/var/folders", "/Applications/Dangerzone.app:/Applications/Dangerzone.app"]
EOF
podman machine init
podman machine set --rootful=false  
podman machine start
```
Then, set the container runtime to podman using this command:

```bash
/Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --set-container-runtime podman
```

In order to get back to the default behaviour (Docker Desktop on macOS), pass
the `default` value instead:

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
