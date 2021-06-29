# Dangerzone VM key

This is an insecure hard-coded SSH key that's built-in to allow ssh access to the VM's `user` account. It was generated like this:

```sh
ssh-keygen -t ed25519 -C dangerzone-vm-key -N "" -f id_ed25519
```
