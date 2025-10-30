# -*- mode: python -*-
import inspect
import os
import platform

p = platform.system()

# Get the version
root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
)
with open(os.path.join(root, "share", "version.txt")) as f:
    version = f.read().strip()

print("Dangerzone version: {}".format(version))

if p == "Darwin":
    datas = [("../../share", "share"), ("../macos/document.icns", ".")]
else:
    datas = [("../../share", "share")]

if p == "Windows":
    icon = os.path.join(root, "share", "dangerzone.ico")
else:
    icon = None

a = Analysis(
    ["dangerzone"],
    pathex=["."],
    binaries=None,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="dangerzone",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name="dangerzone"
)

# The macOS app bundle
if p == "Darwin":
    app = BUNDLE(
        coll,
        name="Dangerzone.app",
        icon="../macos/dangerzone.icns",
        bundle_identifier="press.freedom.dangerzone",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": version,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeExtensions": ["pdf"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["application/pdf"],
                    "CFBundleTypeName": "PDF Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["docx", "doc", "docm"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/msword",
                        "application/vnd.ms-word.document.macroEnabled.12",
                    ],
                    "CFBundleTypeName": "Microsoft Word Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["xlsx", "xls"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-excel",
                    ],
                    "CFBundleTypeName": "Microsoft Excel Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["pptx", "ppt"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "application/vnd.ms-powerpoint",
                    ],
                    "CFBundleTypeName": "Microsoft PowerPoint Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["odt"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.oasis.opendocument.text"
                    ],
                    "CFBundleTypeName": "ODF Text Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["ods"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.oasis.opendocument.spreadsheet"
                    ],
                    "CFBundleTypeName": "ODF Spreadsheet Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["odp"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.oasis.opendocument.presentation"
                    ],
                    "CFBundleTypeName": "ODF Presentation Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["odg"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        "application/vnd.oasis.opendocument.graphics"
                    ],
                    "CFBundleTypeName": "ODF Graphics Document",
                    "CFBundleTypeRole": "Viewer",
                },
                # Commented MIMEs are not used in `file` and don't conform to the rules.
                # Left them for just in case
                {
                    "CFBundleTypeExtensions": ["hwp", "hwpx"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": [
                        # "application/vnd.hancom.hwp",
                        # "application/haansofthwp",
                        "application/x-hwp",
                        # "application/vnd.hancom.hwpx",
                        # "application/haansofthwpx",
                        "application/hwp+zip",
                        "application/x-hwp+zip",
                    ],
                    "CFBundleTypeName": "Hancom Office Document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["epub"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["application/epub+zip"],
                    "CFBundleTypeName": "EPUB document",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["svg"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/svg+xml"],
                    "CFBundleTypeName": "SVG Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["bmp"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/bmp"],
                    "CFBundleTypeName": "BMP Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["pbm"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/x-portable-bitmap"],
                    "CFBundleTypeName": "PBM Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["ppm"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/x-portable-pixmap"],
                    "CFBundleTypeName": "PPM Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["pnm"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/x-portable-anymap"],
                    "CFBundleTypeName": "PNM Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["jpg", "jpeg"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/jpeg"],
                    "CFBundleTypeName": "JPEG Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["gif"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/gif"],
                    "CFBundleTypeName": "GIF Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["png"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/png"],
                    "CFBundleTypeName": "PNG Image",
                    "CFBundleTypeRole": "Viewer",
                },
                {
                    "CFBundleTypeExtensions": ["tif", "tiff"],
                    "CFBundleTypeIconFile": "../macos/document.icns",
                    "CFBundleTypeMIMETypes": ["image/tiff", "image/x-tiff"],
                    "CFBundleTypeName": "TIFF Image",
                    "CFBundleTypeRole": "Viewer",
                },
            ],
        },
    )
