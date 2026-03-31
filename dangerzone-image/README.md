# Dangerzone-image

This repository contains the dangerzone container image that is used to perform "document to pixels" conversions. This container is used by [dangerzone](https://dangerzone.rocks) to securely converst its documents.

## Using the container image

The image is published on a monthly basis on the container registry, alongside their Cosign signatures. 
Additionally, nightly and development branches are published under the `dangerzone-testing` namespace.

| Channel | Location                               | Signed?    | Use it for  |
| ------- | -------------------------------------- | ---------- | ----------- |
| Stable  | `ghcr.io/freedomofpress/dangerzone/v1` | ✅ ([prod keys](/freedomofpress-dangerzone.pub))  | Production  |
| Nightly | `ghcr.io/freedomofpress/dangerzone-testing/main/v1` | ✅ ([testing keys](/tests/assets/dangerzone-testing.pub))  | Development |
| Branch  | `ghcr.io/freedomofpress/dangerzone-testing/<branch-name>/v1` | ✅ ([testing keys](/tests/assets/dangerzone-testing.pub))  | Development |

## What this container provides

This container provides a way to convert documents to pixel buffers, using a secure sandbox.

The security of the sandbox is provided by different layers:

- The container uses [gVisor](/docs/gvisor.md), an application Kernel that provides a strong layer of isolation between running applications and the host operating system. It is written in a memory-safe language (Go) and runs in userspace.
- Additionally, it is expected that this container is run with specific flags and a specific seccomp policy, to unsure that users are not mapped in the container, that no network is available in the container, etc. See the "how to use" section.

We also provide the following guarantees, related to the distribution of the image:

- The container is [signed](/docs/sign-image) in an auditable way, using Cosign
- Ultimately, the container is [reproducible](/docs/reproducibility.md), and so one can verify that it can be rebuilt, resulting to the same digests.

## How to use this container?

The recommanded way to use this container is via these flags. They require to defined a specific seccomp policy. Seccomp policies is a way to define which system calls are authorized inside the container.

Here is a podman command with the proper flags, and [the gvisor seccomp policy](tests/share/seccomp.gvisor.json).

```bash
podman run \\
    --log-driver none \\
    --security-opt no-new-privileges \\
    --userns nomap \\
    --security-opt fseccomp=seccomp.gvisor.json
    --cap-drop all \\
    --cap-add SYS_CHROOT \\
    --security-opt label=type:container_engine_t \\
    --network=none \\
    -u dangerzone \\
    --rm -i ghcr.io/freedomofpress/dangerzone/v1 \\
    /usr/bin/python3 -m dangerzone.conversion.doc_to_pixels
```


## dangerzone-insecure-conversion python package

> [!WARNING]
> Do not use this unless you are certain about what you are doing.
> Do not use this to convert documents that should be processed safely!

The python code that runs inside the container is packaged under the name "dangerzone-insecure-conversion". It's considered insecure because the intended way to run dangerzone is by using a hardened sandbox, which is provided by dangerzone.

With that being said, there are situations where it's useful to run this code on its own, for instance when adding new file formats.

### Running the tests

```bash
uv pip install -e .
uv run pytest

# Or, if you prefer to run the tests outside the sandbox:
uv run pytest --local

# It's also possible to run tests in parallel if you have multiple cores:
uv run --with pytest-xdist pytest -n 6
```
