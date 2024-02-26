#!/bin/sh

# This file runs within the gVisor sandbox.
# Read `entrypoint.py` for why this is needed.

set -euo pipefail

# Move files over from /host-safezone to /safezone.
if [[ "$(ls -1 /host-safezone | wc -l)" -gt 0 ]]; then
	mv /host-safezone/* /safezone/
fi
# chown them as the unprivileged user.
chown -R dangerzone:dangerzone /safezone

# Run the unprivileged command.
set +e
su-exec dangerzone:dangerzone "$@"
retcode="$?"
set -e

# Move files back from /safezone to /host-safezone.
if [[ -d /safezone ]] && [[ "$(ls -1 /safezone | wc -l)" -gt 0 ]]; then
	# chown them back to the user that exists on the host.
	chown -R root:root /safezone
	mv /safezone/* /host-safezone/
fi

# Mirror the exit code of the unprivileged command.
exit "$retcode"
