# Scripted QA

The `dev_scripts/qa.py` script runs the QA steps for a supported platform, in
order to make sure that the dev does not skip something. These steps are taken
from our [release instructions](../../RELEASE.md#qa).

The idea behind this script is that it will present each step to the user and
ask them to perform it manually and specify it passes, in order to continue to
the next one. For specific steps, it allows the user to run them automatically.
In steps that require a Dangerzone dev environment, this script uses the
`env.py` script to create one.

Including all the supported platforms in this script is still a work in
progress.
