"""Tests for the environment variable allowlist in entrypoint.py."""

from dangerzone.container_helpers.entrypoint import allowed_env


def _apply(env: dict[str, str]) -> set[str]:
    """Reproduce the allowlist logic — return forwarded key names."""
    return {k for k in env if k in allowed_env}


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
        assert allowed_env == {"LANG", "LC_ALL", "LC_CTYPE", "LANGUAGE", "TZ"}
