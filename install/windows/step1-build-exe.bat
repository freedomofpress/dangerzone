REM delete old dist and build files
rmdir /s /q dist
rmdir /s /q build

REM build the exe with pyinstaller
pyinstaller install\pyinstaller\pyinstaller.spec

REM code sign dangerzone.exe
signtool.exe sign /v /d "Dangerzone" /sha1 28a4af3b6ba5ed0ef307e1b96a140e1b42450c3b /tr http://timestamp.digicert.com dist\dangerzone\dangerzone.exe
