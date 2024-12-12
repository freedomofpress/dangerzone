###########################################
# Build PyMuPDF

FROM debian:bookworm-20230904-slim as dangerzone-image
ENV DEBIAN_FRONTEND=noninteractive
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  repro-sources-list.sh && \
  apt-get update && \
  apt-get install -y --no-install-recommends python3-fitz libreoffice-nogui libreoffice-java-common python3 python3-magic default-jdk-headless fonts-noto-cjk && \
  : "Clean up for improving reproducibility (optional)" && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache /var/lib/apt/lists/*

RUN mkdir -p /opt/dangerzone/dangerzone && \
  touch /opt/dangerzone/dangerzone/__init__.py && \
  addgroup --gid 1000 dangerzone && \
  adduser --uid 1000 --ingroup dangerzone --shell /bin/true --home /home/dangerzone dangerzone

COPY conversion /opt/dangerzone/dangerzone/conversion

###########################################
# gVisor wrapper image

FROM alpine:latest as gvisor-image

RUN GVISOR_URL="https://storage.googleapis.com/gvisor/releases/release/latest/$(uname -m)"; \
    wget "${GVISOR_URL}/runsc" "${GVISOR_URL}/runsc.sha512" && \
    sha512sum -c runsc.sha512 && \
    rm -f runsc.sha512 && \
    chmod 555 runsc && \
    mv runsc /usr/bin/

###########################################
# gVisor wrapper image

FROM debian:bookworm-20230904-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  --mount=type=bind,source=./repro-sources-list.sh,target=/usr/local/bin/repro-sources-list.sh \
  repro-sources-list.sh && \
  apt-get update && \
  apt-get install -y --no-install-recommends python3 && \
  : "Clean up for improving reproducibility (optional)" && \
  rm -rf /var/log/* /var/cache/ldconfig/aux-cache /var/lib/apt/lists/*

RUN addgroup --gid 1000 dangerzone && \
  adduser --uid 1000 --ingroup dangerzone --shell /bin/true --home /home/dangerzone dangerzone

COPY --from=gvisor-image /usr/bin/runsc /usr/bin/runsc

# Switch to the dangerzone user for the rest of the script.
USER dangerzone

# Copy the Dangerzone image, as created by the previous steps, into the home
# directory of the `dangerzone` user.
RUN mkdir /home/dangerzone/dangerzone-image
COPY --from=dangerzone-image / /home/dangerzone/dangerzone-image/rootfs

# Create a directory that will be used by gVisor as the place where it will
# store the state of its containers.
RUN mkdir /home/dangerzone/.containers

COPY gvisor_wrapper/entrypoint.py /

ENTRYPOINT ["/entrypoint.py"]
