ARG DEBIAN_DATE=20241202

###########################################
# Build Dangerzone container image (inner)

FROM debian:bookworm-${DEBIAN_DATE}-slim as dangerzone-image
ENV DEBIAN_FRONTEND=noninteractive
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./oci/repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  repro-sources-list.sh && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
      python3-fitz libreoffice-nogui libreoffice-java-common python3 \
      python3-magic default-jdk-headless fonts-noto-cjk unzip wget && \
  : "Clean up for improving reproducibility (optional)" && \
  apt-get autoremove -y && \
  rm -rf /var/cache/fontconfig/ && \
  rm -rf /etc/ssl/certs/java/cacerts && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache

# Download H2ORestart from GitHub using a pinned version and hash. Note that
# it's available in Debian repos, but not Bookworm just yet.
ARG H2ORESTART_CHECKSUM=8a5be77359695c14faaf33891d3eca6c9d73c1224599aab50a9d2ccc04640580
ARG H2ORESTART_VERSION=v0.6.8

RUN mkdir /libreoffice_ext && cd libreoffice_ext \
    && H2ORESTART_FILENAME=h2orestart.oxt \
    && wget https://github.com/ebandal/H2Orestart/releases/download/$H2ORESTART_VERSION/$H2ORESTART_FILENAME \
    && echo "$H2ORESTART_CHECKSUM  $H2ORESTART_FILENAME" | sha256sum -c \
    && install -dm777 "/usr/lib/libreoffice/share/extensions/"

RUN mkdir -p /opt/dangerzone/dangerzone && \
  touch /opt/dangerzone/dangerzone/__init__.py && \
  addgroup --gid 1000 dangerzone && \
  adduser --uid 1000 --ingroup dangerzone --shell /bin/true --home /home/dangerzone dangerzone

COPY conversion/doc_to_pixels.py conversion/common.py conversion/errors.py conversion/__init__.py /opt/dangerzone/dangerzone/conversion

####################################
# Build gVisor wrapper image (outer)

FROM debian:bookworm-${DEBIAN_DATE}-slim

ARG GVISOR_DATE=20241202

ENV DEBIAN_FRONTEND=noninteractive
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./oci/repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  --mount=type=bind,source=./oci/gvisor.key,target=/tmp/gvisor.key \
  repro-sources-list.sh && \
  : "Setup APT to install gVisor from its separate APT repo" && \
  apt-get update && \
  apt-get install -y --no-install-recommends apt-transport-https ca-certificates gnupg && \
  gpg -o /usr/share/keyrings/gvisor-archive-keyring.gpg --dearmor /tmp/gvisor.key && \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases ${GVISOR_DATE} main" > /etc/apt/sources.list.d/gvisor.list && \
  : "Install Pthon3 and gVisor" && \
  apt-get update && \
  apt-get install -y --no-install-recommends python3 runsc && \
  : "Clean up for improving reproducibility (optional)" && \
  apt-get remove -y apt-transport-https ca-certificates gnupg && \
  apt-get autoremove -y && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache

RUN addgroup --gid 1000 dangerzone && \
  adduser --uid 1000 --ingroup dangerzone --shell /bin/true --home /home/dangerzone dangerzone

# Switch to the dangerzone user for the rest of the script.
USER dangerzone

# Copy the Dangerzone image, as created by the previous steps, into the home
# directory of the `dangerzone` user.
RUN mkdir /home/dangerzone/dangerzone-image
COPY --from=dangerzone-image / /home/dangerzone/dangerzone-image/rootfs

# Create a directory that will be used by gVisor as the place where it will
# store the state of its containers.
RUN mkdir /home/dangerzone/.containers

COPY oci/entrypoint.py /

ENTRYPOINT ["/entrypoint.py"]
