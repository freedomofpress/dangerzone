REM REM delete old dist and build files
REM rmdir /s /q dist
REM rmdir /s /q build
REM
REM REM build the gui and cli exe
REM python .\setup-windows.py build
REM
REM REM code sign executables
REM signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha256 /t http://time.certum.pl/ ^
REM  build\exe.win-amd64-3.13\dangerzone.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-cli.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-image.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-machine.exe
REM
REM REM verify the signatures of the executables
REM signtool.exe verify /pa ^
REM  build\exe.win-amd64-3.13\dangerzone.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-cli.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-image.exe ^
REM  build\exe.win-amd64-3.13\dangerzone-machine.exe

REM build the wxs file
python install\windows\build-wxs.py

REM build the msi package
cd build
wix build -arch x64 -ext WixToolset.UI.wixext -ext WixToolset.Util.wixext .\Dangerzone.wxs -out Dangerzone.msi

REM REM validate Dangerzone.msi
REM wix msi validate Dangerzone.msi
REM
REM REM code sign Dangerzone.msi
REM signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha256 /t http://time.certum.pl/ Dangerzone.msi
REM
REM REM verify the signature of Dangerzone.msi
REM signtool.exe verify /pa Dangerzone.msi

REM move Dangerzone.msi to dist
cd ..
mkdir dist
move build\Dangerzone.msi dist
