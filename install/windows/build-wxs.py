#!/usr/bin/env python3
import os
import uuid
import xml.etree.ElementTree as ET


def build_data(dirname, dir_prefix, id_, name):
    data = {
        "id": id_,
        "name": name,
        "files": [],
        "dirs": [],
    }

    for basename in os.listdir(dirname):
        filename = os.path.join(dirname, basename)
        if os.path.isfile(filename):
            data["files"].append(os.path.join(dir_prefix, basename))
        elif os.path.isdir(filename):
            if id_ == "INSTALLFOLDER":
                id_prefix = "Folder"
            else:
                id_prefix = id_

            # Skip lib/PySide6/examples folder due to ilegal file names
            if "\\build\\exe.win-amd64-3.12\\lib\\PySide6\\examples" in dirname:
                continue

            # Skip lib/PySide6/qml/QtQuick folder due to ilegal file names
            # XXX Since we're not using Qml it should be no problem
            if "\\build\\exe.win-amd64-3.12\\lib\\PySide6\\qml\\QtQuick" in dirname:
                continue

            id_value = f"{id_prefix}{basename.capitalize().replace('-', '_')}"
            data["dirs"].append(
                build_data(
                    os.path.join(dirname, basename),
                    os.path.join(dir_prefix, basename),
                    id_value,
                    basename,
                )
            )

    if len(data["files"]) > 0:
        if id_ == "INSTALLFOLDER":
            data["component_id"] = "ApplicationFiles"
        else:
            data["component_id"] = "FolderComponent" + id_[len("Folder") :]
        data["component_guid"] = str(uuid.uuid4())

    return data


def build_dir_xml(root, data):
    attrs = {}
    if "id" in data:
        attrs["Id"] = data["id"]
    if "name" in data:
        attrs["Name"] = data["name"]
    el = ET.SubElement(root, "Directory", attrs)
    for subdata in data["dirs"]:
        build_dir_xml(el, subdata)


def build_components_xml(root, data):
    component_ids = []
    if "component_id" in data:
        component_ids.append(data["component_id"])

        if "component_guid" in data:
            dir_ref_el = ET.SubElement(root, "DirectoryRef", Id=data["id"])
            component_el = ET.SubElement(
                dir_ref_el,
                "Component",
                Id=data["component_id"],
                Guid=data["component_guid"],
            )
            for filename in data["files"]:
                file_el = ET.SubElement(
                    component_el, "File", Source=filename, Id="file_" + uuid.uuid4().hex
                )
    for subdata in data["dirs"]:
        component_ids += build_components_xml(root, subdata)

    return component_ids


def main():
    version_filename = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "share",
        "version.txt",
    )
    with open(version_filename) as f:
        # Read the Dangerzone version from share/version.txt, and remove any potential
        # -rc markers.
        version = f.read().strip().split("-")[0]

    dist_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "build",
        "exe.win-amd64-3.12",
    )
    if not os.path.exists(dist_dir):
        print("You must build the dangerzone binary before running this")
        return

    # Prepare data for WiX file harvesting from the output of cx_Freeze
    data = build_data(
        dist_dir,
        "exe.win-amd64-3.12",
        "INSTALLFOLDER",
        "Dangerzone",
    )

    # Add the Wix root element
    wix_el = ET.Element(
        "Wix",
        {
            "xmlns": "http://wixtoolset.org/schemas/v4/wxs",
            "xmlns:ui": "http://wixtoolset.org/schemas/v4/wxs/ui",
        },
    )

    # Add the Package element
    package_el = ET.SubElement(
        wix_el,
        "Package",
        Name="Dangerzone",
        Manufacturer="Freedom of the Press Foundation",
        UpgradeCode="$(var.ProductUpgradeCode)",
        Language="1033",
        Compressed="yes",
        Codepage="1252",
        Version="$(var.ProductVersion)",
    )
    ET.SubElement(
        package_el,
        "SummaryInformation",
        Keywords="Installer",
        Description="Dangerzone $(var.ProductVersion) Installer",
        Codepage="1252",
    )
    ET.SubElement(package_el, "MediaTemplate", EmbedCab="yes")
    ET.SubElement(
        package_el, "Icon", Id="ProductIcon", SourceFile="..\\share\\dangerzone.ico"
    )
    ET.SubElement(package_el, "Property", Id="ARPPRODUCTICON", Value="ProductIcon")
    ET.SubElement(
        package_el,
        "Property",
        Id="ARPHELPLINK",
        Value="https://dangerzone.rocks",
    )
    ET.SubElement(
        package_el,
        "Property",
        Id="ARPURLINFOABOUT",
        Value="https://freedom.press",
    )
    ET.SubElement(
        package_el, "ui:WixUI", Id="WixUI_InstallDir", InstallDirectory="INSTALLFOLDER"
    )
    ET.SubElement(package_el, "UIRef", Id="WixUI_ErrorProgressText")
    ET.SubElement(
        package_el,
        "WixVariable",
        Id="WixUILicenseRtf",
        Value="..\\install\\windows\\license.rtf",
    )
    ET.SubElement(
        package_el,
        "WixVariable",
        Id="WixUIDialogBmp",
        Value="..\\install\\windows\\dialog.bmp",
    )
    ET.SubElement(
        package_el,
        "MajorUpgrade",
        DowngradeErrorMessage="A newer version of [ProductName] is already installed. If you are sure you want to downgrade, remove the existing installation via Programs and Features.",
    )

    # Add the ProgramMenuFolder StandardDirectory
    programmenufolder_el = ET.SubElement(
        package_el,
        "StandardDirectory",
        Id="ProgramMenuFolder",
    )
    # Add a shortcut for Dangerzone in the Start menu
    shortcut_el = ET.SubElement(
        programmenufolder_el,
        "Component",
        Id="ApplicationShortcuts",
        Guid="539e7de8-a124-4c09-aa55-0dd516aad7bc",
    )
    ET.SubElement(
        shortcut_el,
        "Shortcut",
        Id="DangerzoneStartMenuShortcut",
        Name="Dangerzone",
        Description="Dangerzone",
        Target="[INSTALLFOLDER]dangerzone.exe",
        WorkingDirectory="INSTALLFOLDER",
    )
    ET.SubElement(
        shortcut_el,
        "RegistryValue",
        Root="HKCU",
        Key="Software\\Freedom of the Press Foundation\\Dangerzone",
        Name="installed",
        Type="integer",
        Value="1",
        KeyPath="yes",
    )

    # Add the ProgramFilesFolder StandardDirectory
    programfilesfolder_el = ET.SubElement(
        package_el,
        "StandardDirectory",
        Id="ProgramFilesFolder",
    )

    # Create the directory structure for the installed product
    build_dir_xml(programfilesfolder_el, data)

    # Create a component group for application components
    applicationcomponents_el = ET.SubElement(
        package_el, "ComponentGroup", Id="ApplicationComponents"
    )
    # Populate the application components group with components for the installed package
    build_components_xml(applicationcomponents_el, data)

    # Add the Feature element
    feature_el = ET.SubElement(package_el, "Feature", Id="DefaultFeature", Level="1")
    for component_id in component_ids:
        ET.SubElement(feature_el, "ComponentRef", Id=component_id)
    ET.SubElement(feature_el, "ComponentRef", Id="ApplicationShortcuts")

    print(f'<?define ProductVersion = "{version}"?>')
    print('<?define ProductUpgradeCode = "12b9695c-965b-4be0-bc33-21274e809576"?>')
    ET.indent(wix_el, space="    ")
    print(ET.tostring(wix_el).decode())


if __name__ == "__main__":
    main()
