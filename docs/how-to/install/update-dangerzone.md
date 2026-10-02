# Update Dangerzone

Dangerzone gets updates to improve its features _and_ to fix problems, so updating may be the simplest path to resolving an issue you are experiencing.

## Check whether you are up to date

1. Check which version of Dangerzone you are currently using: run Dangerzone, then look for a series of numbers to the right of the logo within the app. The format of the numbers will look similar to `0.4.1`.
2. Now find the latest available version of Dangerzone: go to the [download page](https://dangerzone.rocks/#downloads). Look for the version number displayed.
3. If the version on the Dangerzone download page is higher than the version of your installed app, you should consider updating.

On Windows and macOS, if you enabled update checks, Dangerzone also shows a green dot on the hamburger menu in the top-right corner when a new release is out. Click it and choose **New version available** to see the changelog.

If you're curious about how that works, have a look at the [update notifications](../../explanation/update-notifications.md) section.

## Install the update

=== "macOS"

    Download the new `.dmg` from the [download page](https://dangerzone.rocks/#downloads) and drag Dangerzone into your Applications folder again, as you did for the [initial installation](index.md#macos). Your settings are kept.

    If you installed Dangerzone with [Homebrew](https://brew.sh/), upgrade it the same way:

    ```sh
    brew upgrade --cask dangerzone
    ```

=== "Windows"

    Download the new `.msi` from the [download page](https://dangerzone.rocks/#downloads) and run it, as you did for the [initial installation](index.md#windows). Your settings are kept.

    If you installed Dangerzone with Winget, upgrade it the same way:

    ```powershell
    winget upgrade FreedomofthePressFoundation.Dangerzone
    ```

=== "Ubuntu and Debian"

    ```sh
    sudo apt update
    sudo apt upgrade dangerzone
    ```

    Replace `dangerzone` with `dangerzone-full` if that is the package you installed.

=== "Fedora"

    ```sh
    sudo dnf upgrade dangerzone
    ```

    Replace `dangerzone` with `dangerzone-full` if that is the package you installed. On Fedora Atomic, run `rpm-ostree upgrade` and reboot.

=== "Qubes OS"

    Update the template where you installed `dangerzone-qubes` with `sudo dnf upgrade dangerzone-qubes`, then shut down the template and restart the qubes that use it.

## Updating the sandbox without updating Dangerzone

The sandbox image updates independently from the application. If you enabled automatic updates, Dangerzone fetches new sandbox images on its own. To trigger it by hand, or on an air-gapped machine, see [Update the sandbox image](update-the-sandbox.md).

## Update check errors

When update checks are enabled, Dangerzone contacts GitHub at most once every 12 hours to learn about new releases. If a check fails, a red dot shows up on the hamburger menu in the top-right corner. Click it and choose **Update error** to read the error message.

Most of the time, this means that your computer is not connected to the Internet, or that GitHub is experiencing an outage. Dangerzone tries again on its own 12 hours later, and the error goes away after the next successful check. In the meantime, you can [check by hand](#check-whether-you-are-up-to-date) whether you are up to date.

If the error keeps coming back, or if you are unsure about the message you see, please [report it](../contribute/report-an-issue.md).

If your computer is never online, uncheck **Check for updates** in the hamburger menu to turn the checks off, and follow our releases some other way: on [Mastodon](https://social.freedom.press/@dangerzone), or with the **Watch** button of our [GitHub repository](https://github.com/freedomofpress/dangerzone). To update the sandbox on such a machine, see [Installing image updates to air-gapped environments](update-the-sandbox.md#installing-image-updates-to-air-gapped-environments).
