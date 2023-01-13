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
            if id_ == "INSTALLDIR":
                id_prefix = "Folder"
            else:
                id_prefix = id_

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
        if id_ == "INSTALLDIR":
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

    # If this is the ProgramMenuFolder, add the menu component
    if "id" in data and data["id"] == "ProgramMenuFolder":
        component_el = ET.SubElement(
            el,
            "Component",
            Id="ApplicationShortcuts",
            Guid="539e7de8-a124-4c09-aa55-0dd516aad7bc",
        )
        ET.SubElement(
            component_el,
            "Shortcut",
            Id="ApplicationShortcut1",
            Name="Dangerzone",
            Description="Dangerzone",
            Target="[INSTALLDIR]dangerzone.exe",
            WorkingDirectory="INSTALLDIR",
        )
        ET.SubElement(
            component_el,
            "RegistryValue",
            Root="HKCU",
            Key="Software\First Look Media\Dangerzone",
            Name="installed",
            Type="integer",
            Value="1",
            KeyPath="yes",
        )


def build_components_xml(root, data):
    component_ids = []
    if "component_id" in data:
        component_ids.append(data["component_id"])

    for subdata in data["dirs"]:
        if "component_guid" in subdata:
            dir_ref_el = ET.SubElement(root, "DirectoryRef", Id=subdata["id"])
            component_el = ET.SubElement(
                dir_ref_el,
                "Component",
                Id=subdata["component_id"],
                Guid=subdata["component_guid"],
            )
            for filename in subdata["files"]:
                file_el = ET.SubElement(
                    component_el, "File", Source=filename, Id="file_" + uuid.uuid4().hex
                )

        component_ids += build_components_xml(root, subdata)

    return component_ids


def main():
    version_filename = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "share",
        "version.txt",
    )
    with open(version_filename) as f:
        version = f.read().strip()

    dist_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "build",
        "exe.win-amd64-3.10",
    )
    if not os.path.exists(dist_dir):
        print("You must build the dangerzone binary before running this")
        return

    data = {
        "id": "TARGETDIR",
        "name": "SourceDir",
        "dirs": [
            {
                "id": "ProgramFilesFolder",
                "dirs": [],
            },
            {
                "id": "ProgramMenuFolder",
                "dirs": [],
            },
        ],
    }

    data["dirs"][0]["dirs"].append(
        build_data(
            dist_dir,
            "exe.win-amd64-3.10",
            "INSTALLDIR",
            "Dangerzone",
        )
    )

    root_el = ET.Element("Wix", xmlns="http://schemas.microsoft.com/wix/2006/wi")
    product_el = ET.SubElement(
        root_el,
        "Product",
        Name="Dangerzone",
        Manufacturer="First Look Media",
        Id="*",
        UpgradeCode="$(var.ProductUpgradeCode)",
        Language="1033",
        Codepage="1252",
        Version="$(var.ProductVersion)",
    )
    ET.SubElement(
        product_el,
        "Package",
        Id="*",
        Keywords="Installer",
        Description="Dangerzone $(var.ProductVersion) Installer",
        Manufacturer="First Look Media",
        InstallerVersion="100",
        Languages="1033",
        Compressed="yes",
        SummaryCodepage="1252",
    )
    ET.SubElement(product_el, "Media", Id="1", Cabinet="product.cab", EmbedCab="yes")
    ET.SubElement(
        product_el, "Icon", Id="ProductIcon", SourceFile="..\\share\\dangerzone.ico"
    )
    ET.SubElement(product_el, "Property", Id="ARPPRODUCTICON", Value="ProductIcon")
    ET.SubElement(
        product_el,
        "Property",
        Id="ARPHELPLINK",
        Value="https://dangerzone.rocks",
    )
    ET.SubElement(
        product_el,
        "Property",
        Id="ARPURLINFOABOUT",
        Value="https://tech.firstlook.media",
    )
    ET.SubElement(product_el, "UIRef", Id="WixUI_Minimal")
    ET.SubElement(product_el, "UIRef", Id="WixUI_ErrorProgressText")
    ET.SubElement(
        product_el,
        "WixVariable",
        Id="WixUILicenseRtf",
        Value="..\\install\\windows\\license.rtf",
    )
    ET.SubElement(
        product_el,
        "WixVariable",
        Id="WixUIDialogBmp",
        Value="..\\install\\windows\\dialog.bmp",
    )
    ET.SubElement(
        product_el,
        "MajorUpgrade",
        AllowSameVersionUpgrades="yes",
        DowngradeErrorMessage="A newer version of [ProductName] is already installed. If you are sure you want to downgrade, remove the existing installation via Programs and Features.",
    )

    build_dir_xml(product_el, data)
    component_ids = build_components_xml(product_el, data)

    feature_el = ET.SubElement(product_el, "Feature", Id="DefaultFeature", Level="1")
    for component_id in component_ids:
        ET.SubElement(feature_el, "ComponentRef", Id=component_id)
    ET.SubElement(feature_el, "ComponentRef", Id="ApplicationShortcuts")

    print('<?xml version="1.0" encoding="windows-1252"?>')
    print(f'<?define ProductVersion = "{version}"?>')
    print('<?define ProductUpgradeCode = "12b9695c-965b-4be0-bc33-21274e809576"?>')
    ET.indent(root_el)
    print(ET.tostring(root_el).decode())


if __name__ == "__main__":
    main()
