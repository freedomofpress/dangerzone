REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the exe with pyinstaller
pyinstaller install\pyinstaller\pyinstaller.spec

REM code sign dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /a /tr http://time.certum.pl/ dist\dangerzone\dangerzone.exe
