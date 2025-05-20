# Update notifications

This design document explains how the notification mechanism for Dangerzone
updates works, what are its benefits and limitations, and what other
alternatives we have considered. It has been adapted by discussions on GitHub
issue [#189](https://github.com/freedomofpress/dangerzone/issues/189), and has
been updated to reflect the current design.

A user-facing document on how update notifications work can be found in
https://github.com/freedomofpress/dangerzone/wiki/Updates

## Design overview

A hamburger icon is visible across almost all of the Dangerzone windows, and is used to notify the users when there are new releases.

### First run

_We detect it's the first time Dangerzone runs because the
`settings["updater_last_check"] is None`._

Add the following keys in our `settings.json` file.

* `"updater_check_all": True`: Whether or not to check and apply independent container updates and check for new releases.
* `"updater_last_check": None`: The last time we checked for updates (in seconds
  from Unix epoch). None means that we haven't checked yet.
* `"updater_latest_version": "0.4.2"`: The latest version that the Dangerzone
  updater has detected. By default it's the current version.
* `"updater_latest_changelog": ""`: The latest changelog that the Dangerzone
  updater has detected. By default it's empty.
* `"updater_errors: 0`: The number of update check errors that we have
  encountered in a row.

Previously, `"updater_check"` was used to determine if we should check for new releases, and has been replaced by `"updater_check_all"` when adding support for independent container updates.

### Second run

_We detect it's the second time Dangerzone runs because
`settings["updater_check_all"] is not None and settings["updater_last_check"] is
None`._

Before starting up the main window, the user is prompted if they want to enable update checks.

### Subsequent runs

_We perform the following only if `settings["updater_check_all"] == True`._

1. Spawn a new thread so that we don't block the main window.
2. Check if we have cached information about a release (version and changelog).
   If yes, return those immediately.
3. Check if the last time we checked for new releases was less than 12 hours
   ago. In that case, skip this update check so that we don't leak telemetry
   stats to GitHub.
4. Hit the GitHub releases API and get the [latest release](https://api.github.com/repos/freedomofpress/dangerzone/releases/latest).
   Store the current time as the last check time, even if the call fails.
5. Check if the latest release matches `settings["updater_latest_version"]`. If
   yes, return an empty update report.
6. If a new update has been detected, return the version number and the
   changelog.
7. Add a green bubble in the notification icon, and a menu entry called "New
   version available".
8. Users who click on this entry will see a dialog with more info:

    * Title: "Dangerzone v0.5.0 has been released"
    * Body:

       > A new Dangerzone version been released. Please visit our [downloads page](https://dangerzone.rocks#downloads) to install this update.
       >
       > (Show changelog rendered from Markdown in a collapsible text box)
    * Buttons:
       - OK: Return

Notes:
* Any successful attempt to fetch info from GitHub will result in clearing the
  `settings["updater_errors"]` key.

### Error handling

_We trigger error handling when the updater thread encounters an error (either
due to an HTTPS failure or a Python exception) and does not complete
successfully._

1. Bump the number of errors we've encountered in a row
   (`settings["updater_errors"] += 1`)
2. Return an update report with the error we've encountered.
3. Update the hamburger menu with a red notification bubble, and add a menu
   entry called "Update error".
4. If a user clicks on this menu entry, show a dialog window:
    * Title: "Update check error"
    * Body:

       > Something went wrong while checking for Dangerzone updates:
       >
       > You are strongly advised to visit our [downloads page](https://dangerzone.rocks#downloads) and check for new updates manually, or consult [this page](https://github.com/freedomofpress/dangerzone/wiki/Updates) for common causes of errors . Alternatively, you can uncheck "Check for updates", if you are in an air-gapped environment and have another way of learning about updates.
       >
       > (Show the latest error message in a scrollable, copyable text box)

   * Buttons:
      - Close: Return

## Key Benefits

1. The above approach future-proofs Dangerzone against API changes or bugs in
   the update check process, by asking users to manually visit
   https://dangerzone.rocks.
2. If we want to draw the attention of users to immediately install a release,
   we can do so in the release body, which we will show in a pop-up window.
3. If we are aware of issues that prevent updates, we can add them in the wiki
   page that we show in the error popup. Wiki pages are not versioned, so we can
   add useful info even after a release.

## Security Considerations

Because this approach does not download binaries / auto-updates, it **does not
add any more security issues** than the existing, manual way of installing
updates. These issues have to do with a compromised/malicous GitHub service, and
are the following:

1. GitHub pages can alter the contents of our main site
   (https://dangerzone.rocks)
2. GitHub releases can serve an older, vulnerable version of Dangerzone, instead
   of a new update.
3. GitHub releases can serve a malicious binary (requires a joint operation from
   a malicious CA as well, for extra legitimacy).
4. GitHub releases can silently drop updates.
5. GitHub releases can know which users download Dangerzone updates.
6. Network attackers can know that a user has Dangerzone installed (because we ask the user to visit https://dangerzone.rocks)

A good update framework would probably defend against 1,2,3. This is not to say
that our users are currently unprotected, since 1-4 can be detected by the
general public and the developers (unless GitHub specifically targets an
individual, but that's another story).

## Usability Considerations

1. We do not have an update story for users that only use the Dangerzone CLI. A
   good assumption is that they are on Linux, so they auto-update.

## Alternatives

We researched a bit on this subject and found out that there are update
frameworks that do this job for us. While working on this issue, we decided that
integrating with one framework will certainly take a bit of work, especially
given that we target both Windows and MacOS systems. In the meantime though, we
didn't want to have releases out without including at least a notification
channel, since staying behind on updates has a huge negative impact on the
users' safety.

The update frameworks that we learned about are:

## Sparkle Project

[Sparkle project](https://sparkle-project.org) seems to be the de-facto update
framework in MacOS. Integrators in practice need to care about two things:
creating a proper `Appcast.xml` file on the server-side, and calling the Sparkle
code from the client-side. These are covered in the project's
[documentation](https://sparkle-project.org/documentation/).

The client-side part is not very straight-forward, since Sparkle is written in
Objective-C. Thankfully, there are others who have ventured into this before:
https://fman.io/blog/codesigning-and-automatic-updates-for-pyqt-apps/

The server-side part is also not very straight-forward. For integrators that use
GitHub releases (like us), this issue may be of help:
https://github.com/sparkle-project/Sparkle/issues/648

The Windows platform is not covered by Sparkle itself, but there are other
projects, such as [WinSparkle](https://winsparkle.org/), that follow a similar
approach. I see that there's a [Python library (`pywinsparkle`)](https://pypi.org/project/pywinsparkle/)
for interacting with WinSparkle, so this may alleviate some pains.

Note that the Sparkle project is not a silver bullet. Development missteps can
happen, and users can be left without updates. Here's an [example issue](https://github.com/sparkle-project/Sparkle/issues/345) that showcases this.

## The Update Framework

[The Update Framework](https://theupdateframework.io/) is a graduated CNCF
project hosted by Linux Foundation. It's based on the
[Thandy](https://chromium.googlesource.com/chromium/src.git/+/master/docs/updater/protocol_3_1.md)
updater for Tor. It's [not widely adopted](https://github.com/sparkle-project/Sparkle/issues/345), but some of its
adopters are high-profile, and it has passed security audits.

It's more of a [specification](https://github.com/sparkle-project/Sparkle/issues/345)
and less of a software project, although a well-maintained
[reference implementation](https://github.com/sparkle-project/Sparkle/issues/345)
in Python exists. Also, a [Python project (`tufup`)](https://doc.qt.io/qtinstallerframework/ifw-updates.html)
that builds upon this implementation makes it even easier to generate the
required keys and files.

Regardless of whether we use it, knowing about the [threat vectors](https://theupdateframework.io/security/) that it's protecting against is very important.

## Other Projects

* Qt has some updater framework as well: https://doc.qt.io/qtinstallerframework/ifw-updates.html
* Google Chrome has it's own updater framework: https://chromium.googlesource.com/chromium/src.git/+/master/docs/updater/protocol_3_1.md
* Keepass rolls out its own way to update: https://github.com/keepassxreboot/keepassxc/blob/develop/src/updatecheck/UpdateChecker.cpp
* [PyUpdater](https://github.com/Digital-Sapphire/PyUpdater) was another popular updater project for Python, but is now archived.
