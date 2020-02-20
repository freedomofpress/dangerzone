REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the exe with pyinstaller
pyinstaller install\pyinstaller\pyinstaller.spec

REM TODO: code sign dangerzone.exe

REM build the msi package
cd build
mkdir wix
cd wix
candle.exe ..\..\install\windows\Dangerzone.wxs
light.exe -ext WixUIExtension Dangerzone.wixobj

REM TODO: code sign dangerzone.msi

REM moving dangerzone.msi to dist
cd ..\..
move build\wix\Dangerzone.msi dist
