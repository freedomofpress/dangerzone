###########################################
# Build PyMuPDF

FROM alpine:latest as pymupdf-build

ARG REQUIREMENTS_TXT

# Install PyMuPDF via hash-checked requirements file
COPY ${REQUIREMENTS_TXT} /tmp/requirements.txt
RUN apk --no-cache add linux-headers g++ linux-headers gcc make python3-dev py3-pip clang-dev
RUN pip install --break-system-packages --require-hashes -r /tmp/requirements.txt


###########################################
# Download H2ORestart
FROM alpine:latest as h2orestart-dl
ARG H2ORESTART_CHECKSUM=5db816a1e57b510456633f55e693cb5ef3675ef8b35df4f31c90ab9d4c66071a
RUN mkdir /libreoffice_ext && cd libreoffice_ext \
    && H2ORESTART_FILENAME=h2orestart.oxt \
    && H2ORESTART_VERSION="v0.5.7" \
    && wget https://github.com/ebandal/H2Orestart/releases/download/$H2ORESTART_VERSION/$H2ORESTART_FILENAME \
    && echo "$H2ORESTART_CHECKSUM  $H2ORESTART_FILENAME" | sha256sum -c \
    && install -dm777 "/usr/lib/libreoffice/share/extensions/"


###########################################
# Dangerzone image

FROM alpine:latest

# Install dependencies
RUN apk --no-cache -U upgrade && \
    apk --no-cache add \
    libreoffice \
    openjdk8 \
    python3 \
    py3-magic \
    font-noto-cjk

COPY --from=pymupdf-build /usr/lib/python3.11/site-packages/fitz/ /usr/lib/python3.11/site-packages/fitz
COPY --from=h2orestart-dl /libreoffice_ext/ /libreoffice_ext

RUN install -dm777 "/usr/lib/libreoffice/share/extensions/"

ENV PYTHONPATH=/opt/dangerzone

RUN mkdir -p /opt/dangerzone/dangerzone
RUN touch /opt/dangerzone/dangerzone/__init__.py
COPY conversion /opt/dangerzone/dangerzone/conversion

# Add the unprivileged user
RUN adduser -s /bin/sh -D dangerzone
USER dangerzone
