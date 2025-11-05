REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the gui and cli exe
python .\setup-windows.py build

REM code sign executables
signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha256 /t http://time.certum.pl/ ^
 build\exe.win-amd64-3.13\dangerzone.exe ^
 build\exe.win-amd64-3.13\dangerzone-cli.exe ^
 build\exe.win-amd64-3.13\dangerzone-image.exe ^
 build\exe.win-amd64-3.13\dangerzone-machine.exe

REM verify the signatures of the executables
signtool.exe verify /pa ^
 build\exe.win-amd64-3.13\dangerzone.exe ^
 build\exe.win-amd64-3.13\dangerzone-cli.exe ^
 build\exe.win-amd64-3.13\dangerzone-image.exe ^
 build\exe.win-amd64-3.13\dangerzone-machine.exe

REM build the wxs file
python install\windows\build-wxs.py

REM build the msi package
cd build
wix build -arch x64 -ext WixToolset.UI.wixext .\Dangerzone.wxs -out Dangerzone.msi

REM validate Dangerzone.msi
wix msi validate Dangerzone.msi

REM code sign Dangerzone.msi
signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha256 /t http://time.certum.pl/ Dangerzone.msi

REM verify the signature of Dangerzone.msi
signtool.exe verify /pa Dangerzone.msi

REM move Dangerzone.msi to dist
cd ..
mkdir dist
move build\Dangerzone.msi dist
