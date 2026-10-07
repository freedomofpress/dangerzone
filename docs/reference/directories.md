# Directories

This page lists the directories Dangerzone uses to store data, on each platform.

## Configuration directory

<div class="os-specific" markdown>

=== "macOS"

    📁 **`~/Library/Application Support/dangerzone/`**

    Same as the data directory.

=== "Windows"

    📁 **`%LOCALAPPDATA%\dangerzone\dangerzone\`**

    Same as the data directory.

=== "Linux"

    📁 **`~/.config/dangerzone/`**

    Respects the `XDG_CONFIG_HOME` environment variable.

</div>

`settings.json`
:   The Dangerzone settings. See [Settings](settings.md).

## Data directory

<div class="os-specific" markdown>

=== "macOS"

    📁 **`~/Library/Application Support/dangerzone/`**

    Same as the configuration directory.

=== "Windows"

    📁 **`%LOCALAPPDATA%\dangerzone\dangerzone\`**

    Same as the configuration directory.

=== "Linux"

    📁 **`~/.local/share/dangerzone/`**

    Respects the `XDG_DATA_HOME` environment variable.

</div>

`signatures/`
:   The signatures of the sandbox images that Dangerzone has verified, grouped by the digest of the public key that signed them. See [Independent sandbox updates](../explanation/sandbox-updates.md).

`signatures/last_log_index`
:   The Rekor transparency log index of the installed sandbox image. Dangerzone uses it to refuse older images, and considers the sandbox image as not installed if this file is missing.

## Cache directory

<div class="os-specific" markdown>

=== "macOS"

    📁 **`~/Library/Caches/dangerzone/`**

=== "Windows"

    📁 **`%LOCALAPPDATA%\dangerzone\dangerzone\Cache\`**

=== "Linux"

    📁 **`~/.cache/dangerzone/`**

    Respects the `XDG_CACHE_HOME` environment variable. Dangerzone does not use this directory on Linux.

</div>

Dangerzone regenerates these files as needed, so you can safely delete them.

`containers.conf`
:   The Podman configuration that Dangerzone passes to its bundled Podman via the `CONTAINERS_CONF` environment variable. It is rewritten whenever Dangerzone runs.

`shared/seccomp.gvisor.json`
:   A copy of the seccomp profile of the sandbox. Dangerzone mounts the cache directory read-only into the Podman machine, so that the profile can reach the container.
