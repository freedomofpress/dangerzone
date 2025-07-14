FROM fedora:latest

RUN dnf install -y podman python3 python3-pip python3-tox ssh dropbear make procps ss
RUN rpm --restore shadow-utils

RUN adduser user

RUN echo user:2000:2000 > /etc/subuid
RUN echo user:2000:2000 > /etc/subgid

RUN mkdir -p /etc/dropbear
RUN chmod 777 /etc/dropbear

USER user

RUN mkdir -p ~/.ssh
RUN ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -P ""
RUN cp /home/user/.ssh/id_ed25519.pub home/user/.ssh/authorized_keys

WORKDIR /home/user/podman-py

COPY entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
