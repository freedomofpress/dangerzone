# Dangerzone Testing

Dangerzone has some automated testing under `tests/`.

The following assumes that you have already setup the development environment.

## Run tests

Unit / integration tests are run with:

```bash
poetry run make test
```

## Run large tests

We also have a larger set of tests that can take a day or more to run, where we evaluate the completeness of Dangerzone conversions.

```bash
poetry run make test-large
```

## Run fuzz tests

Security fuzz tests exercise the trust boundary between the container and the
host — specifically, the IPC pixel stream protocol and the PyMuPDF/MuPDF C
layer that processes untrusted pixel data.

```bash
poetry run make fuzz
```

This runs two components:

1. **IPC protocol fuzzer** (`tests/fuzz_ipc_standalone.py`): Generates random
   byte strings and feeds them into the IPC parsing logic that reads pixel
   streams from the container. Tests truncation, boundary values, and malformed
   headers. Runs 10,000 iterations by default.

2. **PyMuPDF boundary tests** (`tests/test_pixmap_fuzzer.py`,
   `tests/test_cve_2026_3308.py`): Exercises `fitz.Pixmap` with adversarial
   dimensions and pixel data, and verifies that dangerzone's dimension bounds
   (MAX_PAGE_WIDTH=10000, MAX_PAGE_HEIGHT=10000) prevent integer overflow in
   MuPDF's stride calculation (CVE-2026-3308).

You can run the standalone fuzzer directly with more iterations or a fixed seed:

```bash
python tests/fuzz_ipc_standalone.py --iterations 50000
python tests/fuzz_ipc_standalone.py --seed 42  # reproducible run
```

### Test report generation
After running the large tests, a report is stored under `tests/test_docs_large/results/junit/` and it is composed of the JUnit XML file describing the pytest run.

This report can be analysed for errors. It is obtained by running:

```bash
cd tests/docs_test_large
make report
```

If you want to run the report on some historical test result, you can call:

```bash
cd tests/docs_test_large
python report.py tests/test_docs_large/results/junit/commit_<COMMIT_ID>.junit.xml
```
