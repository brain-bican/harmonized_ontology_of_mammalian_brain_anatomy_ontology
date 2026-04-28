import argparse
import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path


OWL_NS = "http://www.w3.org/2002/07/owl#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
OBO_NS = "http://purl.obolibrary.org/obo/"

ET.register_namespace("", "http://purl.obolibrary.org/obo/uberon/bridge/uberon-bridge-to-homba.owl#")
ET.register_namespace("obo", OBO_NS)
ET.register_namespace("owl", OWL_NS)
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
ET.register_namespace("xml", "http://www.w3.org/XML/1998/namespace")
ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema#")


OWL = f"{{{OWL_NS}}}"
RDF = f"{{{RDF_NS}}}"

DHBA_CLASS_PREFIX = "https://purl.brain-bican.org/ontology/dhbao/DHBA_"
HOMBA_CLASS_PREFIX = "https://purl.brain-bican.org/ontology/HOMBA_"
ONTOLOGY_IRI = "http://purl.obolibrary.org/obo/uberon/bridge/uberon-bridge-to-homba.owl"
VERSION_IRI = "http://purl.obolibrary.org/obo/uberon/releases/2025-12-04/bridge/uberon-bridge-to-homba.owl"
DEFAULT_HOMBA_JSON = Path(__file__).resolve().parent.parent / "ontology" / "tmp" / "HOMBA.json"


def collect_numeric_homba_ids(homba_json_path: Path) -> set[str]:
    payload = json.loads(homba_json_path.read_text())
    ids = set()

    def walk(node):
        homba_id = node.get("HOMBA_id")
        if homba_id:
            local_id = homba_id.split(":", 1)[-1]
            if local_id.isdigit():
                ids.add(local_id)
        for child in node.get("children", []):
            walk(child)

    walk(payload)
    return ids


def rewrite_subject_about(elem: ET.Element, new_id: str) -> None:
    about_key = f"{RDF}about"
    current = elem.attrib.get(about_key, "")
    if current.startswith(DHBA_CLASS_PREFIX):
        elem.attrib[about_key] = HOMBA_CLASS_PREFIX + new_id


def rewrite_comment_text(elem: ET.Element, new_id: str) -> None:
    if elem.text:
        elem.text = elem.text.replace(DHBA_CLASS_PREFIX + new_id, HOMBA_CLASS_PREFIX + new_id)


def generate_bridge(dhba_bridge_path: Path, homba_json_path: Path, output_path: Path) -> tuple[int, int]:
    homba_numeric_ids = collect_numeric_homba_ids(homba_json_path)
    tree = ET.parse(dhba_bridge_path)
    root = tree.getroot()
    root.attrib["xml:base"] = ONTOLOGY_IRI

    ontology = root.find(f"{OWL}Ontology")
    if ontology is not None:
        ontology.attrib[f"{RDF}about"] = ONTOLOGY_IRI
        version_iri = ontology.find(f"{OWL}versionIRI")
        if version_iri is not None:
            version_iri.attrib[f"{RDF}resource"] = VERSION_IRI

    kept_classes = []
    dropped = 0

    for child in list(root):
        if child.tag == f"{OWL}Class":
            about = child.attrib.get(f"{RDF}about", "")
            match = re.fullmatch(re.escape(DHBA_CLASS_PREFIX) + r"([0-9A-Z]+)", about)
            if match:
                local_id = match.group(1)
                if local_id.isdigit() and local_id in homba_numeric_ids:
                    kept = deepcopy(child)
                    rewrite_subject_about(kept, local_id)
                    kept_classes.append(kept)
                else:
                    dropped += 1
                continue
        elif child.tag is ET.Comment:
            continue

    # Remove all DHBA class/comment blocks, then append the rewritten HOMBA classes.
    new_children = []
    for child in list(root):
        if child.tag == f"{OWL}Class":
            about = child.attrib.get(f"{RDF}about", "")
            if about.startswith(DHBA_CLASS_PREFIX):
                continue
        if child.tag is ET.Comment and child.text and DHBA_CLASS_PREFIX in child.text:
            continue
        new_children.append(child)

    root[:] = new_children + kept_classes

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return len(kept_classes), dropped


def main():
    parser = argparse.ArgumentParser(description="Generate an initial HOMBA bridge from the DHBA bridge.")
    parser.add_argument(
        "--dhba-bridge",
        default="uberon-bridge-to-dhba.owl",
        help="Path to the source DHBA bridge file.",
    )
    parser.add_argument(
        "--homba-json",
        default=str(DEFAULT_HOMBA_JSON),
        help="Path to the local HOMBA structure graph JSON.",
    )
    parser.add_argument(
        "--output",
        default="uberon-bridge-to-homba.owl",
        help="Path for the generated HOMBA bridge file.",
    )
    args = parser.parse_args()

    kept, dropped = generate_bridge(Path(args.dhba_bridge), Path(args.homba_json), Path(args.output))
    print(f"Generated {args.output} with {kept} HOMBA class mappings; dropped {dropped} DHBA-specific class mappings.")


if __name__ == "__main__":
    main()
