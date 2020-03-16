REM build the msi package
cd build
mkdir wix
cd wix
candle.exe ..\..\install\windows\Dangerzone.wxs
light.exe -ext WixUIExtension Dangerzone.wixobj

REM code sign dangerzone.msi
signtool.exe sign /v /d "Dangerzone" /a /tr http://time.certum.pl/ Dangerzone.msi

REM moving Dangerzone.msi to dist
cd ..\..
move build\wix\Dangerzone.msi dist
