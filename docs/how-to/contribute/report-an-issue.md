# Report an issue

This guide explains where and how to report a problem with Dangerzone.

## Security issues

**Please do not report security vulnerabilities through public GitHub issues.** If you believe you have found a vulnerability, follow the [security policy](../../reference/security-policy.md): it lists the private channels, what we consider in scope, and the timelines we commit to.

## Check the obvious first

1. Make sure you run the latest version. Many reports are fixed by updating, see [Update Dangerzone](../install/update-dangerzone.md).
2. Search the [existing issues](https://github.com/freedomofpress/dangerzone/issues?q=is%3Aissue) for the error message you see. Add a comment to an existing issue rather than opening a duplicate.
3. Skim the [FAQ](../../explanation/faq.md).

## Collect the details

A useful report contains:

* The Dangerzone version (shown next to the logo in the application, or with `dangerzone-cli --version`).
* Your operating system and version, and how you installed Dangerzone (installer, Homebrew, Winget, `.deb`, `.rpm`, Qubes, Tails).
* What you did, what you expected, and what happened instead.
* The exact error message. The graphical application shows a log window on failures, that's what we need.

### Details about the sandbox

Oftentimes, issues are related to Podman (the tool we use to run the converrsion sandbox). In these cases, it's very useful to have a lot of details about it.

=== "Windows"

    Please copy and paste the following commands in your terminal, and provide us with the output:

    ```shell
    'C:\Program Files\Dangerzone\dangerzone-machine.exe' start
    'C:\Program Files\Dangerzone\dangerzone-machine.exe' --log-level debug raw version
    'C:\Program Files\Dangerzone\dangerzone-machine.exe' --log-level debug raw info -f json
    'C:\Program Files\Dangerzone\dangerzone-machine.exe' --log-level debug raw images
    'C:\Program Files\Dangerzone\dangerzone-machine.exe' --log-level debug raw run hello-world
    ```

    Additionally, if you tried to do a conversion, paste the output of this command:

    ```sh
    'C:\Program Files\Dangerzone\dangerzonecli.exe' --debug the-document.pdf
    ```
  
=== "macOS"

    Please copy and paste the following commands in your terminal, and provide us with the output:

      ```shell
      /Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine start
      /Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine --log-level debug raw version
      /Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine --log-level debug raw info -f 'json'
      /Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine --log-level debug raw images
      /Applications/Dangerzone.app/Contents/MacOS/dangerzone-machine --log-level debug raw run hello-world
      ```
      
    Additionally, if you tried to do a conversion, paste the output of this command:

    ```sh
    /Applications/Dangerzone.app/Contents/MacOS/dangerzone-cli --debug the-document.pdf
    ```

=== "Linux"

    Please copy and paste the following commands in your terminal, and provide us with the output:

    ```shell
    podman version
    podman info -f 'json'
    podman images
    podman run hello-world
    ```
  
    Additionally, if you tried to do a conversion, propose the output of this command:

    ```sh
    dangerzone-cli --debug the-document.pdf
    ```

!!! warning "Don't attach the suspicious document"

    The document that failed to convert may be the problem, and it may be malicious. Don't attach it to a public issue. Describe it instead (format, size, how it was produced).

## Open the issue

Open a new issue in the [GitHub tracker](https://github.com/freedomofpress/dangerzone/issues/new) with the details above. We triage issues regularly and may ask follow-up questions, so keep an eye on notifications. If you don't have or don't want to create a Github account to report an issue, you can also contact us via email at  `support@dangerzone.rocks`.

For problems with the sandbox image itself (a document format that doesn't convert, a missing font, a CVE in a bundled tool), the [dangerzone-image](https://github.com/freedomofpress/dangerzone-image/issues) repository is the right place. When in doubt, report to the main repository and we will move it.

## Other channels

* Release announcements and short updates are posted on [Mastodon](https://social.freedom.press/@dangerzone).
* General questions can also go to the issue tracker or in [our discussion board](https://github.com/freedomofpress/dangerzone/discussions).
