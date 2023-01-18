#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PyTest Wrapper script - temporary solution to tests failing non-deterministically [1]
# This is only fixed in podman v4.3.0. The wrapper essentially runs the tests in sequence
# when the podman version is lower.
#
# [1]: https://github.com/freedomofpress/dangerzone/issues/217

# FIXME this whole script should be removed and the respective Makefile calling line
# replaced once all supported platforms have a podman version >= v4.3.0.

import re
import subprocess
import sys

import pytest
from pkg_resources import parse_version

from dangerzone.isolation_provider.container import Container

PODMAN_MIN_VERSION = "4.3.0"


def get_podman_version():
    result = subprocess.run(
        ["podman", "version", "--format", "'{{.Client.Version}}'"], capture_output=True
    )
    version = result.stdout.decode()[:-1]  # trim trailing \n
    return version.split("-dev")[0]  # exclude "-dev" suffix from version


def run_tests_in_parallel(pytest_args):
    args = pytest_args + ["-n", "4"]
    exit_code = pytest.main(args)


def run_tests_in_sequence(pytest_args):
    print("running tests sequentially")
    exit_code = pytest.main(pytest_args)


if __name__ == "__main__":

    pytest_args = sys.argv[1:]  # exclude program names

    if Container.get_runtime_name() == "docker":
        run_tests_in_parallel(pytest_args)
    else:
        podman_ver_minimum_parallel = parse_version(PODMAN_MIN_VERSION)
        podman_ver_current = parse_version(get_podman_version())
        if podman_ver_current >= podman_ver_minimum_parallel:
            run_tests_in_parallel(pytest_args)
        else:
            run_tests_in_sequence(pytest_args)
