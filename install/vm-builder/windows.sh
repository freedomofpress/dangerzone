#!/bin/sh

VAGRANT_FILES=$(find /vagrant -type f | grep -v /vagrant/.vagrant | grep -v /vagrant/vm)
DANGERZONE_CONVERTER_FILES=$(find /opt/dangerzone-converter -type f)

for FILE in $VAGRANT_FILES; do dos2unix $FILE; done
for FILE in $DANGERZONE_CONVERTER_FILES; do dos2unix $FILE; done

/vagrant/build-iso.sh

for FILE in $VAGRANT_FILES; do unix2dos $FILE; done
for FILE in $DANGERZONE_CONVERTER_FILES; do unix2dos $FILE; done
