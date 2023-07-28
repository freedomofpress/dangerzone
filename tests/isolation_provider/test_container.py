import itertools
import json
from typing import Any, Dict

from pytest_mock import MockerFixture

from dangerzone.document import Document
from dangerzone.isolation_provider.container import Container

from .. import sanitized_text, uncommon_text


def test_parse_progress(
    uncommon_text: str, sanitized_text: str, mocker: MockerFixture
) -> None:
    """Test that the `parse_progress()` function handles escape sequences properly."""
    container = Container(enable_timeouts=False)
    container.progress_callback = mocker.MagicMock()
    print_progress_mock = mocker.patch.object(container, "_print_progress")
    d = Document()

    # Test 1 - Check that normal JSON values are printed as is.
    simple_json = json.dumps({"text": "text", "error": False, "percentage": 0})
    container.parse_progress(d, simple_json)
    print_progress_mock.assert_called_with(d, False, "UNTRUSTED> text", 0)

    # Test 2 - Check that a totally invalid string is reported as a failure. If this
    # string contains escape characters, they should be sanitized as well.
    def assert_invalid_json(text: str) -> None:
        print_progress_mock.assert_called_with(
            d, True, f"Invalid JSON returned from container:\n\n\tUNTRUSTED> {text}", -1
        )

    # Try first with a trivially invalid string.
    invalid_json = "()"
    container.parse_progress(d, invalid_json)
    assert_invalid_json(invalid_json)

    # Try next with an invalid string that contains uncommon text.
    container.parse_progress(d, uncommon_text)
    assert_invalid_json(sanitized_text)

    # Test 3 - Check that a structurally valid JSON value with escape characters in it
    # is sanitized.
    valid_json = json.dumps({"text": uncommon_text, "error": False, "percentage": 0})
    sanitized_json = json.dumps(
        {"text": sanitized_text, "error": False, "percentage": 0}
    )
    container.parse_progress(d, valid_json)
    print_progress_mock.assert_called_with(d, False, "UNTRUSTED> " + sanitized_text, 0)

    # Test 4 - Check that a structurally valid JSON, that otherwise does not have the
    # expected keys, or the expected value types, is reported as an error, and any
    # escape sequences are sanitized.

    keys = ["text", "error", "percentage", uncommon_text]
    values = [uncommon_text, False, 0, None]
    possible_kvs = list(itertools.product(keys, values, repeat=1))

    # Based on the above keys and values, create any combination possible, from 0 to 3
    # elements. Take extra care to:
    #
    # * Remove combinations with non-unique keys.
    # * Ignore the sole valid combination (see `valid_json`), since we have already
    #   tested it above.
    for i in range(len(keys)):
        for combo in itertools.combinations(possible_kvs, i):
            dict_combo: Dict[str, Any] = dict(combo)  # type: ignore [arg-type]
            if len(combo) == len(dict_combo.keys()):
                bad_json = json.dumps(dict_combo)
                sanitized_json = bad_json.replace(uncommon_text, sanitized_text)
                if bad_json == valid_json:
                    continue
                container.parse_progress(d, bad_json)
                assert_invalid_json(sanitized_json)
