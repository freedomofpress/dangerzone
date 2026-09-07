# Explanation

Explanation pages discuss and clarify. They give the background needed to
understand why Dangerzone is built the way it is, what it protects against,
and which alternatives were considered. Nothing here is required reading to
use Dangerzone. Everything here helps you trust it, or improve it, with your
eyes open.

<div class="grid cards" markdown>

-   __[What is Dangerzone?](what-is-dangerzone.md)__

    ---

    The idea in plain words, who it is for, and how it compares with
    similar tools.

-   __[When should I use Dangerzone?](when-to-use-dangerzone.md)__

    ---

    A decision guide: the situations where Dangerzone is the right tool,
    and the ones where it isn't.

-   __[Frequently asked questions](faq.md)__

    ---

    Short answers about safe PDFs, OCR, watermarks, the command line,
    browser viewers, images, and more.

-   __[How Dangerzone works](how-dangerzone-works.md)__

    ---

    The document-to-pixels-to-PDF pipeline, the sandbox around it, and the
    role of Podman, gVisor, and disposable qubes.

-   __[Security model](security-model.md)__

    ---

    What Dangerzone promises, what it assumes about attackers, and how the
    layers of defense fit together.

-   __[Independent sandbox updates](sandbox-updates.md)__

    ---

    Why the sandbox image updates separately from the application, and how
    Cosign, Sigstore, and build attestations keep that trustworthy.

-   __[Update notifications](update-notifications.md)__

    ---

    The design of the release notification mechanism, its security and
    usability trade-offs, and the update frameworks we looked at.

-   __[Reproducible builds](reproducible-builds.md)__

    ---

    Which build artifacts are reproducible today and the mechanisms that
    make the Debian packages byte-identical.

-   __[Qubes OS integration](qubes-integration.md)__

    ---

    How the native Qubes OS integration converts documents in disposable
    qubes, and how it differs from the container path.

-   __[Code architecture](architecture.md)__

    ---

    A map of the source tree: entry points, core, isolation providers,
    updater, Podman machines, GUI.

-   __[Create Dangerzone environments](development-environments.md)__

    ---

    How the containerized dev environments deal with nested containers,
    GUI apps, caching, and state.

-   __[The Dangerzone repositories](project-repositories.md)__

    ---

    A bird's-eye view of the repositories and sites that make up the
    project, and how a release flows through them.

</div>
