import docker


def main():
    client = docker.DockerClient(base_url="unix://dangerzone-state/guest.00000948")


if __name__ == "__main__":
    main()
