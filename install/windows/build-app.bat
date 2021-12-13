REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the exe
python .\setup-windows.py build

REM code sign dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /sha1 28a4af3b6ba5ed0ef307e1b96a140e1b42450c3b /tr http://timestamp.digicert.com build\exe.win32-3.9\dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /sha1 28a4af3b6ba5ed0ef307e1b96a140e1b42450c3b /tr http://timestamp.digicert.com build\exe.win32-3.9\dangerzone-cli.exe

REM build the wix file
python install\windows\build-wxs.py > build\Dangerzone.wxs

REM build the msi package
cd build
candle.exe Dangerzone.wxs
light.exe -ext WixUIExtension Dangerzone.wixobj

REM code sign dangerzone.msi
insignia.exe -im Dangerzone.msi
signtool.exe sign /v /d "Dangerzone" /sha1 28a4af3b6ba5ed0ef307e1b96a140e1b42450c3b /tr http://timestamp.digicert.com Dangerzone.msi

REM moving Dangerzone.msi to dist
cd ..
mkdir dist
move build\Dangerzone.msi dist
