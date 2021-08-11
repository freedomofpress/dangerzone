REM Build ISO
cd install\vm-builder
vagrant up
vagrant ssh -- dos2unix /vagrant/windows.sh
vagrant ssh -- /vagrant/windows.sh
vagrant halt
cd ..\..

REM Copy the ISO to resources
mkdir share\vm
cp install\vm-builder\vm\dangerzone.iso share\vm
