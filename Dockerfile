# NOTE: Updating the packages to their latest versions requires bumping the
# Dockerfile args below. For more info about this file, read
# docs/developer/reproducibility.md.

ARG DEBIAN_IMAGE_DATE=20250113

FROM debian:bookworm-${DEBIAN_IMAGE_DATE}-slim as dangerzone-image

ARG GVISOR_ARCHIVE_DATE=20250113
ARG DEBIAN_ARCHIVE_DATE=20250120
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

# XXX: Create a new root hierarchy, that will be used in the final container
# image:
#
# /bin -> usr/bin
# /lib -> usr/lib
# /lib64 -> usr/lib64
# /root
# /run
# /tmp
# /usr -> /home/dangerzone/dangerzone-image/rootfs/usr/
#
# We have to create this hierarchy beforehand because we want to use the same
# /usr for both the inner and outer container. The problem though is that /usr
# is very sensitive, and you can't manipulate in a live system. That is, I
# haven't found a way to do the following, or something equivalent:
#
#    rm -r /usr && ln -s /home/dangerzone/dangerzone-image/rootfs/usr/ /usr
#
# So, we prefer to create the symlinks here instead, and create the image
# manually in the next steps.
RUN mkdir /new_root
RUN mkdir /new_root/root /new_root/run /new_root/tmp
RUN chmod 777 /new_root/tmp
RUN ln -s /home/dangerzone/dangerzone-image/rootfs/usr/ /new_root/usr
RUN ln -s usr/bin /new_root/bin
RUN ln -s usr/lib /new_root/lib
RUN ln -s usr/lib64 /new_root/lib64
RUN ln -s usr/sbin /new_root/sbin

# Intermediate layer

FROM debian:bookworm-${DEBIAN_IMAGE_DATE}-slim as debian-utils

## Final image

FROM scratch

# Copy the filesystem hierarchy that we created in the previous layer, so that
# /usr can be a symlink.
COPY --from=dangerzone-image /new_root/ /

# Copy some files that are necessary to use the outer container image, e.g., in
# order to run `apt`. We _could_ avoid doing this, but the space cost is very
# small.
COPY --from=dangerzone-image /etc/ /etc/
COPY --from=debian-utils /var/ /var/

# Copy the bare minimum to run Dangerzone in the inner container image.
COPY --from=dangerzone-image /etc/ /home/dangerzone/dangerzone-image/rootfs/etc/
COPY --from=dangerzone-image /usr/ /home/dangerzone/dangerzone-image/rootfs/usr/
COPY --from=dangerzone-image /opt/ /home/dangerzone/dangerzone-image/rootfs/opt/
RUN ln -s usr/bin /home/dangerzone/dangerzone-image/rootfs/bin
RUN ln -s usr/lib /home/dangerzone/dangerzone-image/rootfs/lib
RUN ln -s usr/lib64 /home/dangerzone/dangerzone-image/rootfs/lib64

# Allow our entrypoint script to make changes in the following folders.
RUN chown dangerzone:dangerzone /home/dangerzone /home/dangerzone/dangerzone-image/

# Switch to the dangerzone user for the rest of the script.
USER dangerzone

COPY container_helpers/entrypoint.py /

ENTRYPOINT ["/entrypoint.py"]
