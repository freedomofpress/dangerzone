# NOTE: Updating the packages to their latest versions requires bumping the
# Dockerfile args below. For more info about this file, read
# docs/developer/reproducibility.md.

ARG DEBIAN_IMAGE_DATE=20250113

FROM debian:bookworm-${DEBIAN_IMAGE_DATE}-slim as dangerzone-image

ARG GVISOR_ARCHIVE_DATE=20250120
ARG DEBIAN_ARCHIVE_DATE=20250127
ARG H2ORESTART_CHECKSUM=7760dc2963332c50d15eee285933ec4b48d6a1de9e0c0f6082946f93090bd132
ARG H2ORESTART_VERSION=v0.7.0

ENV DEBIAN_FRONTEND=noninteractive

# The following way of installing packages is taken from
# https://github.com/reproducible-containers/repro-sources-list.sh/blob/master/Dockerfile.debian-12,
# and adapted to allow installing gVisor from each own repo as well.
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./container_helpers/repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  --mount=type=bind,source=./container_helpers/gvisor.key,target=/tmp/gvisor.key \
  : "Hacky way to set a date for the Debian snapshot repos" && \
  touch -d ${DEBIAN_ARCHIVE_DATE} /etc/apt/sources.list.d/debian.sources && \
  touch -d ${DEBIAN_ARCHIVE_DATE} /etc/apt/sources.list && \
  repro-sources-list.sh && \
  : "Setup APT to install gVisor from its separate APT repo" && \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y --no-install-recommends apt-transport-https ca-certificates gnupg && \
  gpg -o /usr/share/keyrings/gvisor-archive-keyring.gpg --dearmor /tmp/gvisor.key && \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases ${GVISOR_ARCHIVE_DATE} main" > /etc/apt/sources.list.d/gvisor.list && \
  : "Install the necessary gVisor and Dangerzone dependencies" && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
      python3 python3-fitz libreoffice-nogui libreoffice-java-common \
      python3 python3-magic default-jre-headless fonts-noto-cjk fonts-dejavu \
      runsc unzip wget && \
  : "Clean up for improving reproducibility (optional)" && \
  rm -rf /var/cache/fontconfig/ && \
  rm -rf /etc/ssl/certs/java/cacerts && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache

# Download H2ORestart from GitHub using a pinned version and hash. Note that
# it's available in Debian repos, but not in Bookworm yet.
RUN mkdir /opt/libreoffice_ext && cd /opt/libreoffice_ext \
    && H2ORESTART_FILENAME=h2orestart.oxt \
    && wget https://github.com/ebandal/H2Orestart/releases/download/$H2ORESTART_VERSION/$H2ORESTART_FILENAME \
    && echo "$H2ORESTART_CHECKSUM  $H2ORESTART_FILENAME" | sha256sum -c \
    && install -dm777 "/usr/lib/libreoffice/share/extensions/" \
    && rm /root/.wget-hsts

# Create an unprivileged user both for gVisor and for running Dangerzone.
RUN addgroup --gid 1000 dangerzone
RUN adduser --uid 1000 --ingroup dangerzone --shell /bin/true \
    --disabled-password --home /home/dangerzone dangerzone

# Copy Dangerzone's conversion logic under /opt/dangerzone, and allow Python to
# import it.
RUN mkdir -p /opt/dangerzone/dangerzone
RUN touch /opt/dangerzone/dangerzone/__init__.py

# Copy only the Python code, and not any produced .pyc files.
COPY conversion/*.py /opt/dangerzone/dangerzone/conversion/

# Create a directory that will be used by gVisor as the place where it will
# store the state of its containers.
RUN mkdir /home/dangerzone/.containers

###############################################################################
#
#                       REUSING CONTAINER IMAGES:
#                          Anatomy of a hack
#                       ========================
#
# The rest of the Dockerfile aims to do one thing: allow the final container
# image to actually contain two container images; one for the outer container
# (spawned by Podman/Docker Desktop), and one for the inner container (spawned
# by gVisor).
#
# This has already been done in the past, and we explain why and how in the
# design document for gVisor integration (should be in
# `docs/developer/gvisor.md`). In this iteration, we want to also
# achieve the following:
#
# 1. Have a small final image, by sharing some system paths between the inner
#    and outer container image using symlinks.
# 2. Allow our security scanning tool to see the contents of the inner
#    container image.
# 3. Make the outer container image operational, in the sense that you can use
#    `apt` commands and perform a conversion with Dangerzone, outside the
#    gVisor sandbox. This is helpful for debugging purposes.
#
# Below we'll explain how our design choices are informed by the above
# sub-goals.
#
# First, to achieve a small container image, we basically need to copy `/etc`,
# `/usr` and `/opt` from the original Dangerzone image to the **inner**
# container image (under `/home/dangerzone/dangerzone-image/rootfs/`)
#
# That's all we need. The rest of the files play no role, and we can actually
# mask them in gVisor's OCI config.
#
# Second, in order to let our security scanner find the installed packages,
# we need to copy the following dirs to the root of the **outer** container
# image:
# * `/etc`, so that the security scanner can detect the image type and its
#   sources
# * `/var`, so that the security scanner can have access to the APT database.
#
# IMPORTANT: We don't symlink the `/etc` of the **outer** container image to
# the **inner** one, in order to avoid leaking files like
# `/etc/{hostname,hosts,resolv.conf}` that Podman/Docker mounts when running
# the **outer** container image.
#
# Third, in order to have an operational Debian image, we are _mostly_ covered
# by the dirs we have copied. There's a _rare_ case where during debugging, we
# may want to install a system package that has components in `/etc` and
# `/var`, which will not be available in the **inner** container image. In that
# case, the developer can do the necessary symlinks in the live container.
#
#                           FILESYSTEM HIERARCHY
#                           ====================
#
# The above plan leads to the following filesystem hierarchy:
#
# Outer container image:
#
#     # ls -l /
#     lrwxrwxrwx   1 root   root       7 Jan 27 10:46 bin -> usr/bin
#     -rwxr-xr-x   1 root   root    7764 Jan 24 08:14 entrypoint.py
#     drwxr-xr-x   1 root   root    4096 Jan 27 10:47 etc
#     drwxr-xr-x   1 root   root    4096 Jan 27 10:46 home
#     lrwxrwxrwx   1 root   root       7 Jan 27 10:46 lib -> usr/lib
#     lrwxrwxrwx   1 root   root       9 Jan 27 10:46 lib64 -> usr/lib64
#     drwxr-xr-x   2 root   root    4096 Jan 27 10:46 root
#     drwxr-xr-x   1 root   root    4096 Jan 27 10:47 run
#     lrwxrwxrwx   1 root   root       8 Jan 27 10:46 sbin -> usr/sbin
#     drwxrwxrwx   2 root   root    4096 Jan 27 10:46 tmp
#     lrwxrwxrwx   1 root   root      44 Jan 27 10:46 usr -> /home/dangerzone/dangerzone-image/rootfs/usr
#     drwxr-xr-x  11 root   root    4096 Jan 27 10:47 var
#
# Inner container image:
#
#     # ls -l /home/dangerzone/dangerzone-image/rootfs/
#     total 12
#     lrwxrwxrwx  1 root root    7 Jan 27 10:47 bin -> usr/bin
#     drwxr-xr-x 43 root root 4096 Jan 27 10:46 etc
#     lrwxrwxrwx  1 root root    7 Jan 27 10:47 lib -> usr/lib
#     lrwxrwxrwx  1 root root    9 Jan 27 10:47 lib64 -> usr/lib64
#     drwxr-xr-x  4 root root 4096 Jan 27 10:47 opt
#     drwxr-xr-x 12 root root 4096 Jan 27 10:47 usr
#
#                           SYMLINKING /USR
#                           ===============
#
# It's surprisingly difficult (maybe even borderline impossible), to symlink
# `/usr` to a different path during image build. The problem is that /usr
# is very sensitive, and you can't manipulate it in a live system. That is, I
# haven't found a way to do the following, or something equivalent:
#
#    rm -r /usr && ln -s /home/dangerzone/dangerzone-image/rootfs/usr/ /usr
#
# The `ln` binary, even if you specify it by its full path, cannot run
# (probably because `ld-linux.so` can't be found). For this reason, we have
# to create the symlinks beforehand, in a previous build stage. Then, in an
# empty contianer image (scratch images), we can copy these symlinks and the
# /usr, and stich everything together.
###############################################################################

# Create the filesystem hierarchy that will be used to symlink /usr.

RUN mkdir /new_root
RUN mkdir /new_root/root /new_root/run /new_root/tmp
RUN chmod 777 /new_root/tmp
RUN ln -s /home/dangerzone/dangerzone-image/rootfs/usr /new_root/usr
RUN ln -s usr/bin /new_root/bin
RUN ln -s usr/lib /new_root/lib
RUN ln -s usr/lib64 /new_root/lib64
RUN ln -s usr/sbin /new_root/sbin

## Final image

FROM scratch

# Copy the filesystem hierarchy that we created in the previous stage, so that
# /usr can be a symlink.
COPY --from=dangerzone-image /new_root/ /

# Copy the bare minimum to run Dangerzone in the inner container image.
COPY --from=dangerzone-image /etc/ /home/dangerzone/dangerzone-image/rootfs/etc/
COPY --from=dangerzone-image /opt/ /home/dangerzone/dangerzone-image/rootfs/opt/
COPY --from=dangerzone-image /usr/ /home/dangerzone/dangerzone-image/rootfs/usr/
RUN ln -s usr/bin /home/dangerzone/dangerzone-image/rootfs/bin
RUN ln -s usr/lib /home/dangerzone/dangerzone-image/rootfs/lib
RUN ln -s usr/lib64 /home/dangerzone/dangerzone-image/rootfs/lib64

# Copy the bare minimum to let the security scanner find vulnerabilities.
COPY --from=dangerzone-image /etc/ /etc/
COPY --from=dangerzone-image /var/ /var/

# Allow our entrypoint script to make changes in the following folders.
RUN chown dangerzone:dangerzone /home/dangerzone /home/dangerzone/dangerzone-image/

# Switch to the dangerzone user for the rest of the script.
USER dangerzone

COPY container_helpers/entrypoint.py /

ENTRYPOINT ["/entrypoint.py"]
