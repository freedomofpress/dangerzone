# Dangerzone Testing

Dangerzone has some automated testing under `tests/`.

The following assumes that you have already setup the development environment.

## Run tests

Unit / integration tests are run with:

```bash
poetry run make test
```

## Run a subset

The `test` target wraps `pytest`, so you can call it directly with the usual selectors:

```bash
poetry run pytest tests/test_cli.py
poetry run pytest -k "ocr" -v
```

## Lint and type-check

CI runs the same checks as:

```bash
poetry run make lint
```

Most formatting issues can be fixed automatically with:

```bash
poetry run make fix
```

## Test on another Linux distribution

To run the tests inside a clean container for any supported Debian, Ubuntu, or Fedora release, see [Use the containerized dev environments](dev-environments.md).
