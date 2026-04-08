"""Tests for the environment variable allowlist in entrypoint.py.

The entrypoint builds an OCI config for gVisor and forwards only allowlisted
environment variables into the sandbox.  Since entrypoint.py has module-level
side effects and can't be imported, we parse its AST to extract the allowlist
and test the filtering logic here.
"""

import ast
import pathlib

ENTRYPOINT = pathlib.Path(__file__).parent.parent / (
    "dangerzone/container_helpers/entrypoint.py"
)


def _read_allowlist() -> set[str]:
    """Extract the allowed_env set from entrypoint.py via AST."""
    tree = ast.parse(ENTRYPOINT.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "allowed_env"
            and isinstance(node.value, ast.Set)
        ):
            return {
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    raise AssertionError("Could not find 'allowed_env = {...}' in entrypoint.py")


ALLOWED_ENV = _read_allowlist()


def _apply(env: dict[str, str]) -> set[str]:
    """Reproduce the allowlist logic — return forwarded key names."""
    return {k for k in env if k in ALLOWED_ENV}


class TestEnvAllowlist:
    def test_forwards_locale_and_tz(self) -> None:
        env = {"LANG": "en_US.UTF-8", "LC_ALL": "C", "TZ": "UTC"}
        assert _apply(env) == {"LANG", "LC_ALL", "TZ"}

    def test_blocks_sensitive_vars(self) -> None:
        env = {
            "AWS_SECRET_ACCESS_KEY": "x",
            "GITHUB_TOKEN": "x",
            "ANTHROPIC_API_KEY": "x",
        }
        assert _apply(env) == set()

    def test_blocks_unknown_vars(self) -> None:
        env = {"MY_CUSTOM_VAR": "x", "SOME_SECRET": "x"}
        assert _apply(env) == set()

    def test_mixed_env_only_passes_allowed(self) -> None:
        env = {
            "LANG": "en_US.UTF-8",
            "HOME": "/home/user",
            "PATH": "/usr/bin",
            "AWS_SECRET_ACCESS_KEY": "x",
            "TZ": "America/Los_Angeles",
        }
        assert _apply(env) == {"LANG", "TZ"}

    def test_allowlist_contains_expected_vars(self) -> None:
        """Sanity check: the allowlist has exactly the locale + TZ vars."""
        assert ALLOWED_ENV == {"LANG", "LC_ALL", "LC_CTYPE", "LANGUAGE", "TZ"}
