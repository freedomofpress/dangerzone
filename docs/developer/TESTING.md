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

Two layers, each with its own test file:

1. **Layer 1 — IPC protocol fuzzer** (`tests/isolation_provider/fuzz_ipc.py`):
   Random byte strings fed into the real `read_int` / `read_bytes` from
   `dangerzone.isolation_provider.base` and the matching
   `DangerzoneConverter._write_int` encoder used by the `Dummy` provider's
   `dummy_script`. Tests truncation, boundary values, and malformed headers.
   10,000 iterations by default.

2. **Layer 2 — PyMuPDF boundary tests**
   (`tests/isolation_provider/test_pixmap_boundaries.py`,
   `tests/isolation_provider/test_cve_2026_3308.py`): Parametrized
   regression tests that exercise `fitz.Pixmap` with adversarial dimensions
   and pixel data, and verify that dangerzone's dimension bounds
   (`MAX_PAGE_WIDTH=10000`, `MAX_PAGE_HEIGHT=10000`) prevent integer
   overflow in MuPDF's stride calculation (CVE-2026-3308).

You can run the fuzzer directly with more iterations or a fixed seed:

```bash
python tests/isolation_provider/fuzz_ipc.py --iterations 50000
python tests/isolation_provider/fuzz_ipc.py --seed 42  # reproducible run
```

### Fuzzing best practices

The fuzz tests in this repo are lightweight random fuzzers (not
coverage-guided). For background on fuzzing techniques and tooling:

- [OpenSSF Fuzzing Initiative](https://openssf.org/technical-initiatives/fuzzing/)
- [Google - Introduction to Fuzzing](https://github.com/google/fuzzing/blob/master/docs/intro-to-fuzzing.md)
- [The Fuzzing Book](https://www.fuzzingbook.org/) — comprehensive reference on
  generating software tests, including grammar-based and mutation-based fuzzing

For coverage-guided fuzzing of the IPC protocol, consider
[Atheris](https://github.com/google/atheris) (Python) or writing a C harness
for MuPDF's `fz_unpack_stream` with [libFuzzer](https://llvm.org/docs/LibFuzzer.html).

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
