# NOTE: The following Dockerfile attempts to mimic a regular user with sudo
# powers, who installs Dangerzone. It starts with a regular Debian/Ubuntu image,
# adds a user with sudo powers, and then runs our installation instructions, as
# presented in our INSTALL.md.
#
# For more info on how to use this Dockerfile locally, check
# .github/workflows/check_repos.yml.

ARG DISTRO
ARG VERSION

FROM ${DISTRO}:${VERSION}

# Create a user with sudo powers.
RUN apt-get update && apt-get install -y sudo adduser

RUN addgroup user
RUN addgroup wheel
RUN adduser --ingroup user --shell /bin/true \
    --disabled-password --home /home/user user
RUN adduser user wheel

RUN echo "%wheel ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers

USER user
WORKDIR /home/user

# Now run the installation instructions
RUN sudo apt-get update && sudo apt-get install -y gpg ca-certificates
RUN sudo mkdir -p /etc/apt/keyrings
RUN sudo gpg --keyserver hkps://keys.openpgp.org \
    --no-default-keyring --no-permission-warning --homedir $(mktemp -d) \
    --keyring gnupg-ring:/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg \
    --recv-keys DE28AB241FA48260FAC9B8BAA7C9B38522604281
RUN sudo chmod +r /etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg
RUN . /etc/os-release && echo "deb [signed-by=/etc/apt/keyrings/fpf-apt-tools-archive-keyring.gpg] \
    https://packages-r2-prod.freedom.press/apt-tools-prod ${VERSION_CODENAME?} main" \
    | sudo tee /etc/apt/sources.list.d/fpf-apt-tools.list

RUN sudo apt-get update
RUN sudo apt-get install -y dangerzone
