#!/usr/bin/env bash
set -e
dropbear -ER

exec "$@"
