This folder contains signature-folders used for the testing the signatures implementation.

The following folders are used:

- `valid`: this folder contains signatures which should be considered valid and generated with the key available at `tests/assets/test.pub.key`
- `invalid`: this folder contains signatures which should be considered invalid, because their format doesn't match the expected one. e.g. it uses plain text instead of base64-encoded text.
- `tempered`: This folder contain signatures which have been tempered-with. The goal is to have signatures that looks valid, but actually aren't.
