# Dangerzone Testing

Dangerzone has some automated testing under `tests/`.

The following assumes that you have already setup the development environment.

## Run tests

Unit / integration tests are run with:

```bash
uv run make test
```

## Run large tests

We also have a larger set of tests that can take a day or more to run, where we evaluate the completeness of Dangerzone conversions.

```bash
uv run make test-large
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
