# Change Log

## Dangerzone 0.2

- Command line support and improved terminal output
- Additional container hardening
- Fix macOS crash on quit
- Fix --custom-container CLI argument

## Dangerzone 0.1.5

- Add support for macOS Big Sur
- Drop support for Ubuntu 19.10

## Dangerzone 0.1.4

- Suppress confusing stderr output, and fix bug when converting specific documents
- Switch from PyQt5 to PySide2
- Improve Windows and Mac packaging
- Add support for Fedora 32

## Dangerzone 0.1.3

- Add support for Ubuntu 20.04 LTS (#79)
- Prevent crash in macOS if specific PDF viewers are installed (#75)

## Dangerzone 0.1.2 (Linux only)

- Add support for Ubuntu 18.04 LTS

## Dangerzone 0.1.1

- Fix macOS bug that caused a crash on versions earlier than Catalina
- Fix macOS app bundle ODF extensions (`.ods .odt`)
- Allow Linux users to type their password instead of adding their user to the `docker` group
- Use Docker instead of Podman in Fedora
- Allow the use of either OS-packaged Docker or Docker CE in Linux
- Allow opening `.docm` files
- Allow using a custom container for testing

## Dangerzone 0.1

- First release