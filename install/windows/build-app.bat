REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the exe
python .\setup-windows.py build

REM code sign dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha1 /t http://time.certum.pl/ build\exe.win-amd64-3.11\dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha1 /t http://time.certum.pl/ build\exe.win-amd64-3.11\dangerzone-cli.exe

REM build the wix file
python install\windows\build-wxs.py > build\Dangerzone.wxs

REM build the msi package
cd build
candle.exe Dangerzone.wxs
light.exe -ext WixUIExtension Dangerzone.wixobj

REM code sign dangerzone.msi
insignia.exe -im Dangerzone.msi
signtool.exe sign /v /d "Dangerzone" /a /n "Freedom of the Press Foundation" /fd sha1 /t http://time.certum.pl/ Dangerzone.msi

REM moving Dangerzone.msi to dist
cd ..
mkdir dist
move build\Dangerzone.msi dist
