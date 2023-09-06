FROM alpine:edge

ARG TESSDATA_CHECKSUM=990fffb9b7a9b52dc9a2d053a9ef6852ca2b72bd8dfb22988b0b990a700fd3c7
ARG H2ORESTART_CHECKSUM=5db816a1e57b510456633f55e693cb5ef3675ef8b35df4f31c90ab9d4c66071a

# Install dependencies
RUN apk --no-cache -U upgrade && \
    apk --no-cache add \
    ghostscript \
    graphicsmagick \
    libreoffice \
    openjdk8 \
    poppler-utils \
    poppler-data \
    python3 \
    py3-magic \
    tesseract-ocr \
    font-noto-cjk

# Download the trained models from the latest GitHub release of Tesseract, and
# store them under /usr/share/tessdata. This is basically what distro packages
# do under the hood.
#
# Because the GitHub release contains more files than just the trained models,
# we use `find` to fetch only the '*.traineddata' files in the top directory.
#
# Before we untar the models, we also check if the checksum is the expected one.
RUN mkdir tessdata && cd tessdata \
    && TESSDATA_VERSION=$(wget -O- -nv https://api.github.com/repos/tesseract-ocr/tessdata/releases/latest \
        | sed -n 's/^.*"tag_name": "\([0-9.]\+\)".*$/\1/p') \
    && wget https://github.com/tesseract-ocr/tessdata/archive/$TESSDATA_VERSION/tessdata-$TESSDATA_VERSION.tar.gz \
    && echo "$TESSDATA_CHECKSUM  tessdata-$TESSDATA_VERSION.tar.gz" | sha256sum -c \
    && tar -xzvf tessdata-$TESSDATA_VERSION.tar.gz -C . \
    && find . -name '*.traineddata' -maxdepth 2 -exec cp {} /usr/share/tessdata \; \
    && cd .. && rm -r tessdata

RUN mkdir /libreoffice_ext && cd libreoffice_ext \
    && H2ORESTART_FILENAME=h2orestart.oxt \
    && H2ORESTART_VERSION="v0.5.7" \
    && wget https://github.com/ebandal/H2Orestart/releases/download/$H2ORESTART_VERSION/$H2ORESTART_FILENAME \
    && echo "$H2ORESTART_CHECKSUM  $H2ORESTART_FILENAME" | sha256sum -c \
    && install -dm777 "/usr/lib/libreoffice/share/extensions/"

ENV PYTHONPATH=/opt/dangerzone

RUN mkdir -p /opt/dangerzone/dangerzone
RUN touch /opt/dangerzone/dangerzone/__init__.py
COPY conversion /opt/dangerzone/dangerzone/conversion

# Add the unprivileged user
RUN adduser -s /bin/sh -D dangerzone
USER dangerzone

# /tmp/input_file is where the first convert expects the input file to be, and
# /tmp where it will write the pixel files
#
# /dangerzone is where the second script expects files to be put by the first one
#
# /safezone is where the wrapper eventually moves the sanitized files.
VOLUME /dangerzone /tmp/input_file /safezone
