# Report an issue

This guide explains where and how to report a problem with Dangerzone so
that it can be acted on.

## Security issues

**Please do not report security vulnerabilities through public GitHub
issues.** If you believe you have found a vulnerability, follow the
[security policy](../reference/security-policy.md): it lists the private
channels, what we consider in scope, and the timelines we commit to.

## Check the obvious first

1. Make sure you run the latest version. Many reports are fixed by updating,
   see [Update Dangerzone](update-dangerzone.md).
2. Search the [existing issues](https://github.com/freedomofpress/dangerzone/issues?q=is%3Aissue)
   for the error message you see. Add a comment to an existing issue rather
   than opening a duplicate.
3. Skim the [FAQ](../explanation/faq.md).

## Collect the details

A useful report contains:

* The Dangerzone version (shown next to the logo in the application, or with
  `dangerzone-cli --version`).
* Your operating system and version, and how you installed Dangerzone
  (installer, Homebrew, Winget, `.deb`, `.rpm`, Qubes, Tails).
* What you did, what you expected, and what happened instead.
* The exact error message. The graphical application shows a log window on
  failures. The CLI prints errors to the terminal.
* For conversion failures, the output of the CLI with `--debug`, which
  includes the sandbox (gVisor) logs:

    ```sh
    dangerzone-cli --debug the-document.pdf
    ```

    On macOS and Windows, see the [dangerzone-cli reference](../reference/cli/dangerzone-cli.md#location)
    for the full path of the command.

!!! warning "Don't attach the suspicious document"

    The document that failed to convert may be the problem, and it may be
    malicious. Don't attach it to a public issue. Describe it instead (format,
    size, how it was produced), and say whether you can share it privately
    with a maintainer if asked.

## Open the issue

Open a new issue in the
[GitHub tracker](https://github.com/freedomofpress/dangerzone/issues/new)
with the details above. Maintainers triage issues regularly and may ask
follow-up questions, so keep an eye on notifications.

For problems with the sandbox image itself (a document format that doesn't
convert, a missing font, a CVE in a bundled tool), the
[dangerzone-image](https://github.com/freedomofpress/dangerzone-image/issues)
repository is the right place. When in doubt, report to the main repository
and maintainers will move it.

## Other channels

* Release announcements and short updates are posted on
  [Mastodon](https://social.freedom.press/@dangerzone).
* General questions can also go to the issue tracker. Use the `question`
  label.
