#!/usr/bin/env python3

import glob
import sys
import xml.etree.ElementTree as ET


def combine_xmls(xml_files, output_file):
    # Initialize accumulators for summary numbers
    total_errors = 0
    total_failures = 0
    total_skipped = 0
    total_tests = 0
    total_time = 0.0

    # Create the root element for the output XML
    testsuites_elem = ET.Element("testsuites")

    # Prepare a base testsuite element that will contain all testcases
    combined_testsuite = ET.Element("testsuite", name="combined")

    for xml_file in xml_files:
        print(f"Parsing '{xml_file}'")

        try:
            tree = ET.parse(xml_file)
        except ET.ParseError as e:
            print(f"Error parsing {xml_file}: {e}")
            continue

        root = tree.getroot()
        # Assuming structure: <testsuites><testsuite ...>
        testsuite_elem = root.find("testsuite")
        if testsuite_elem is None:
            print(f"No <testsuite> element found in {xml_file}")
            continue

        # Sum up the attributes from each testsuite.
        total_errors += int(testsuite_elem.attrib.get("errors", "0"))
        total_failures += int(testsuite_elem.attrib.get("failures", "0"))
        total_skipped += int(testsuite_elem.attrib.get("skipped", "0"))
        total_tests += int(testsuite_elem.attrib.get("tests", "0"))
        total_time += float(testsuite_elem.attrib.get("time", "0.0"))

        # Move all <testcase> subelements to our combined testsuite.
        for testcase in testsuite_elem.findall("testcase"):
            combined_testsuite.append(testcase)

    # Update the attributes of the combined testsuite
    combined_testsuite.attrib["errors"] = str(total_errors)
    combined_testsuite.attrib["failures"] = str(total_failures)
    combined_testsuite.attrib["skipped"] = str(total_skipped)
    combined_testsuite.attrib["tests"] = str(total_tests)
    combined_testsuite.attrib["time"] = str(total_time)
    # Optionally add a timestamp or hostname you want to combine from the originals.

    # Append the combined testsuite to the testsuites root element.
    testsuites_elem.append(combined_testsuite)

    # Write out the combined XML file.
    tree_out = ET.ElementTree(testsuites_elem)
    tree_out.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Combined XML written to {output_file}")


if __name__ == "__main__":
    # For instance, if all XML files are stored in the "xml_results" directory
    folder = sys.argv[1]
    output = sys.argv[2]
    print(
        f"Will search for XML files in '{folder}' and create a combined XML in"
        f" '{output}'"
    )
    xml_files = glob.glob(f"{folder}/*.xml")
    print("Found len(list(xml_files)) XML file(s)")
    combine_xmls(xml_files, output)
