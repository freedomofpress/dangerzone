def pytest_addoption(parser):
    parser.addoption(
        "--train", action="store_true", help="Enable training of large document set"
    )
    parser.addoption("--long", action="store_true", help="Enable large training set")
