#!/bin/bash
#
#   Copyright The repro-sources-list.sh Authors.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# -----------------------------------------------------------------------------
# repro-sources-list.sh:
# configures /etc/apt/sources.list and similar files for installing packages from a snapshot.
#
# This script is expected to be executed inside Dockerfile.
#
# The following distributions are supported:
# - debian:11    (/etc/apt/sources.list)
# - debian:12    (/etc/apt/sources.list.d/debian.sources)
# - ubuntu:22.04 (/etc/apt/sources.list)
# - ubuntu:24.04 (/etc/apt/sources.listd/ubuntu.sources)
# - archlinux    (/etc/pacman.d/mirrorlist)
#
# For the further information, see https://github.com/reproducible-containers/repro-sources-list.sh
# -----------------------------------------------------------------------------

set -eux -o pipefail

. /etc/os-release

: "${KEEP_CACHE:=1}"

keep_apt_cache() {
	rm -f /etc/apt/apt.conf.d/docker-clean
	echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache
}

case "${ID}" in
"debian")
	: "${SNAPSHOT_ARCHIVE_BASE:=http://snapshot.debian.org/archive/}"
	: "${BACKPORTS:=}"
	if [ -e /etc/apt/sources.list.d/debian.sources ]; then
		: "${SOURCE_DATE_EPOCH:=$(stat --format=%Y /etc/apt/sources.list.d/debian.sources)}"
		rm -f /etc/apt/sources.list.d/debian.sources
	else
		: "${SOURCE_DATE_EPOCH:=$(stat --format=%Y /etc/apt/sources.list)}"
	fi
	snapshot="$(printf "%(%Y%m%dT%H%M%SZ)T\n" "${SOURCE_DATE_EPOCH}")"
	# TODO: use the new format for Debian >= 12
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}debian/${snapshot} ${VERSION_CODENAME} main" >/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}debian-security/${snapshot} ${VERSION_CODENAME}-security main" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}debian/${snapshot} ${VERSION_CODENAME}-updates main" >>/etc/apt/sources.list
	if [ "${BACKPORTS}" = 1 ]; then echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}debian/${snapshot} ${VERSION_CODENAME}-backports main" >>/etc/apt/sources.list; fi
	if [ "${KEEP_CACHE}" = 1 ]; then keep_apt_cache; fi
	;;
"ubuntu")
	: "${SNAPSHOT_ARCHIVE_BASE:=http://snapshot.ubuntu.com/}"
	if [ -e /etc/apt/sources.list.d/ubuntu.sources ]; then
		: "${SOURCE_DATE_EPOCH:=$(stat --format=%Y /etc/apt/sources.list.d/ubuntu.sources)}"
		rm -f /etc/apt/sources.list.d/ubuntu.sources
	else
		: "${SOURCE_DATE_EPOCH:=$(stat --format=%Y /etc/apt/sources.list)}"
	fi
	snapshot="$(printf "%(%Y%m%dT%H%M%SZ)T\n" "${SOURCE_DATE_EPOCH}")"
	# TODO: use the new format for Ubuntu >= 24.04
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME} main restricted" >/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-updates main restricted" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME} universe" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-updates universe" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME} multiverse" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-updates multiverse" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-backports main restricted universe multiverse" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-security main restricted" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-security universe" >>/etc/apt/sources.list
	echo "deb [check-valid-until=no] ${SNAPSHOT_ARCHIVE_BASE}ubuntu/${snapshot} ${VERSION_CODENAME}-security multiverse" >>/etc/apt/sources.list
	if [ "${KEEP_CACHE}" = 1 ]; then keep_apt_cache; fi
	# http://snapshot.ubuntu.com is redirected to https, so we have to install ca-certificates
	export DEBIAN_FRONTEND=noninteractive
	apt-get -o Acquire::https::Verify-Peer=false update >&2
	apt-get -o Acquire::https::Verify-Peer=false install -y ca-certificates >&2
	;;
"arch")
	: "${SNAPSHOT_ARCHIVE_BASE:=http://archive.archlinux.org/}"
	: "${SOURCE_DATE_EPOCH:=$(stat --format=%Y /var/log/pacman.log)}"
	export SOURCE_DATE_EPOCH
	# shellcheck disable=SC2016
	date -d "@${SOURCE_DATE_EPOCH}" "+Server = ${SNAPSHOT_ARCHIVE_BASE}repos/%Y/%m/%d/\$repo/os/\$arch" >/etc/pacman.d/mirrorlist
	;;
*)
	echo >&2 "Unsupported distribution: ${ID}"
	exit 1
	;;
esac

: "${WRITE_SOURCE_DATE_EPOCH:=/dev/null}"
echo "${SOURCE_DATE_EPOCH}" >"${WRITE_SOURCE_DATE_EPOCH}"
echo "SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}"
