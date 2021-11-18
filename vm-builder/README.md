# Build the Dangerzone VM for running podman

## Build the ISO

You need vagrant: `brew install vagrant`

```sh
vagrant up
vagrant ssh -- /vagrant/build-iso.sh
vagrant destroy
```

This takes awhile to run. It:

- Builds a new `dangerzone-converter` docker image
- Builds an ISO, which includes a copy of this image
- Outputs files in the `vm` folder

## Run the VM

```sh
./run-vm.sh
```

# How the VM works

