import argparse
import re
from pathlib import Path


TARGET_XML_BASE = "http://purl.obolibrary.org/obo/uberon/bridge/uberon-bridge-to-homba.owl"


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

    output_path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description="Normalize a downloaded HOMBA bridge RDF/XML file.")
    parser.add_argument("input", help="Input RDF/XML file")
    parser.add_argument("output", help="Output normalized RDF/XML file")
    args = parser.parse_args()
    normalize_bridge(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
