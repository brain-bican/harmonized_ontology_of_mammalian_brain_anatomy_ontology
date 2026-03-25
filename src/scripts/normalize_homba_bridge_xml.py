import argparse
import re
from pathlib import Path
import xml.etree.ElementTree as ET


TARGET_XML_BASE = "http://purl.obolibrary.org/obo/uberon/bridge/uberon-bridge-to-homba.owl"
BFO_PART_OF = "http://purl.obolibrary.org/obo/BFO_0000050"
NCBITAXON_PREFIX = "http://purl.obolibrary.org/obo/NCBITaxon_"
BRIDGE_EQUIVALENCE_BLACKLIST = {
    "https://purl.brain-bican.org/ontology/HOMBA_12810",
    "https://purl.brain-bican.org/ontology/HOMBA_146034836",
}

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
OBO_NS = "http://purl.obolibrary.org/obo/"

NS = {
    "rdf": RDF_NS,
    "rdfs": RDFS_NS,
    "owl": OWL_NS,
    "obo": OBO_NS,
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def _resource(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    return element.attrib.get(f"{{{RDF_NS}}}resource")


def _about(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    return element.attrib.get(f"{{{RDF_NS}}}about")


def _is_part_of_taxon_restriction(subclass_of: ET.Element) -> bool:
    restriction = subclass_of.find("owl:Restriction", NS)
    if restriction is None:
        return False

    return _resource(restriction.find("owl:onProperty", NS)) == BFO_PART_OF and bool(
        (_resource(restriction.find("owl:someValuesFrom", NS)) or "").startswith(NCBITAXON_PREFIX)
    )


def normalize_bridge(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text()

    # Repair duplicate xml:base attributes on the root rdf:RDF element by
    # replacing any existing xml:base assignments with a single canonical one.
    text = re.sub(r'\s+xml:base="[^"]*"', "", text, count=0)
    text = text.replace(
        "<rdf:RDF ",
        f'<rdf:RDF xml:base="{TARGET_XML_BASE}" ',
        1,
    )

    root = ET.fromstring(text)
    for cls in root.findall("owl:Class", NS):
        class_iri = _about(cls)

        if class_iri in BRIDGE_EQUIVALENCE_BLACKLIST:
            for equivalent_class in list(cls.findall("owl:equivalentClass", NS)):
                cls.remove(equivalent_class)

        for subclass_of in list(cls.findall("rdfs:subClassOf", NS)):
            if _is_part_of_taxon_restriction(subclass_of):
                cls.remove(subclass_of)

    ET.ElementTree(root).write(output_path, encoding="unicode", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description="Normalize a downloaded HOMBA bridge RDF/XML file.")
    parser.add_argument("input", help="Input RDF/XML file")
    parser.add_argument("output", help="Output normalized RDF/XML file")
    args = parser.parse_args()
    normalize_bridge(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
