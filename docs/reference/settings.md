# Settings

Dangerzone stores its settings in a JSON file named `settings.json`. The
graphical application writes it whenever you change a setting, and reads it on
start. Missing keys are filled with their defaults, so you can delete the file
to reset everything.

## Location

| Platform | Path |
| -------- | ---- |
| Linux | `~/.config/dangerzone/settings.json` |
| macOS | `~/Library/Application Support/dangerzone/settings.json` |
| Windows | `%LOCALAPPDATA%\dangerzone\dangerzone\settings.json` |

The directory is the per-user configuration directory returned by
[platformdirs](https://platformdirs.readthedocs.io/) for the `dangerzone`
application.

## Keys

### Conversion

`save`
:   Boolean. Default `true`. Whether to save the safe PDF to disk.

`archive`
:   Boolean. Default `true`. Move the original document into an `unsafe/`
    subdirectory after a successful conversion. Corresponds to the "Move
    original documents to 'unsafe' subdirectory" choice in the GUI.

`safe_extension`
:   String. Default `"-safe.pdf"`. Suffix appended to the original name to
    form the output name. Must end with `.pdf`.

`output_dir`
:   String or `null`. Default `null`. Directory where safe PDFs are saved when
    "Save safe PDFs to" is selected. `null` means next to the original.

`ocr`
:   Boolean. Default `true`. Run OCR on the safe PDF.

`ocr_language`
:   String. Default `"English"`. Display name of the OCR language, as listed
    in `share/ocr-languages.json`.

`open`
:   Boolean. Default `true`. Open the safe PDF after conversion.

`open_app`
:   String or `null`. Default `null`. On Linux, the desktop application used
    to open the safe PDF. `null` means the default PDF viewer.

### Container runtime

`container_runtime`
:   String, absent by default. Full path of the container runtime to use
    instead of the platform default. Set with
    `dangerzone-cli --set-container-runtime` and removed with
    `--set-container-runtime default`. See
    [Use Podman Desktop or a custom runtime](../how-to/use-podman-desktop.md).

`stop_other_podman_machines`
:   String. Default `"ask"`. What to do on macOS and Windows when another
    Podman machine is already running, since only one can run at a time.
    `"ask"` prompts, `"always"` stops the other machine, `"never"` makes
    Dangerzone quit instead. The prompt's "Remember my choice" checkbox sets
    this to `"always"` or `"never"`.

### Updates

`updater_check_all`
:   Boolean or `null`. Default `null`. Whether to check for and apply
    independent sandbox updates and to check for new releases. `null` means
    the user has not been asked yet. Replaces the older `updater_check` key.

`updater_ask_before_download`
:   Boolean. Default `true`. Ask before downloading a new sandbox image when
    one is available. The "Always download sandbox updates" checkbox in that
    prompt sets it to `false`.

`updater_last_check`
:   Integer or `null`. Default `null`. Last update check, in seconds since the
    Unix epoch. `null` means Dangerzone has never checked. Checks are spaced
    at least 12 hours apart.

`updater_latest_version`
:   String. Default: the running version. Latest release version that the
    updater has seen.

`updater_latest_changelog`
:   String. Default `""`. Changelog of the latest release seen, rendered in the
    "New version available" dialog.

`updater_remote_log_index`
:   Integer. Default `0`. Rekor transparency log index of the latest sandbox
    image seen in the registry. Used to detect that a newer image exists.

`updater_errors`
:   Integer. Default `0`. Number of consecutive update check errors. Reset to
    `0` on the next successful check.

See [Update notifications](../explanation/update-notifications.md) for how
these keys drive the update flow.

## Related files

Next to the settings, Dangerzone keeps the sandbox image signatures under the
per-user data directory (`~/.local/share/dangerzone/signatures` on Linux,
`~/Library/Application Support/dangerzone/signatures` on macOS,
`%LOCALAPPDATA%\dangerzone\dangerzone\signatures` on Windows), including the
`last_log_index` file that `dangerzone-image load-archive` checks before
installing an archive.
