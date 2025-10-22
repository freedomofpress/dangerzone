This folder contains signature-folders used for the testing the signatures implementation.

The following folders are used:

- `valid`: this folder contains signatures which should be considered valid and generated with the key available at `tests/assets/test.pub.key`
- `invalid`: this folder contains signatures which should be considered invalid, because their format doesn't match the expected one. e.g. it uses plain text instead of base64-encoded text.
- `tampered`: This folder contain signatures which have been tampered-with. The goal is to have signatures that looks valid, but actually aren't. Their format is correct but what's contained inside isn't matching the signatures.
