import argparse
import csv
import json
from pathlib import Path
from string import Template


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "db_graph_atlas.yaml"
OUTPUT_PATH = SCRIPT_DIR.parent / "templates" / "linkouts.tsv"
ATLAS_LINK = Template("http://atlas.brain-map.org/atlas?atlas=$atlas_id#structure=$structure_id")


def is_local_homba_term(node_id, prefix):
    return prefix and str(node_id).startswith(prefix) and not str(node_id).endswith("_ENTITY")


def is_numeric_homba_id(local_id):
    # Numeric HOMBA accessions correspond to DHBA terms; AA accessions are HOMBA-only groupings.
    return str(local_id).isdigit()


def parse_scalar(value):
    value = value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    return value


def load_simple_yaml(path):
    config = {}
    current_section = None
    current_atlas = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            config[current_section] = {"atlases": []}
            current_atlas = None
            continue

        if current_section is None:
            continue

        if indent == 2 and stripped.endswith(":"):
            continue

        if indent == 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            config[current_section][key.strip()] = parse_scalar(value)
            continue

        if indent == 4 and stripped.startswith("-"):
            current_atlas = {}
            config[current_section]["atlases"].append(current_atlas)
            remainder = stripped[1:].strip()
            if remainder:
                key, value = remainder.split(":", 1)
                current_atlas[key.strip()] = parse_scalar(value)
            continue

        if indent == 6 and ":" in stripped and current_atlas is not None:
            key, value = stripped.split(":", 1)
            current_atlas[key.strip()] = parse_scalar(value)

    return config


parser = argparse.ArgumentParser(description="Generate HOMBA linkout template.")
parser.add_argument("filepath", help="Path to the json version of the ontology")
args = parser.parse_args()

with open(args.filepath, "r") as f:
    ontology_json = json.loads(f.read())

graph = ontology_json["graphs"][0]
mapping = load_simple_yaml(CONFIG_PATH)

seed = {
    "ID": "ID",
    "dhba_xref": "A OboInOwl:hasDbXref",
    "atlas_link": "A rdfs:seeAlso",
    "atlas_link_label": ">A rdfs:label",
    "prefLabel": "A skos:prefLabel",
}

tab = [seed]

for node in graph["nodes"]:
    if node.get("type") != "CLASS" or "lbl" not in node:
        continue

    node_id = str(node["id"])
    pref_label = node["lbl"]
    tab.append({"ID": node_id, "dhba_xref": "", "atlas_link": "", "atlas_link_label": "", "prefLabel": pref_label})

    for _, cfg in mapping.items():
        prefix = cfg.get("prefix")
        if not is_local_homba_term(node_id, prefix):
            continue

        local_id = node_id.rsplit("_", 1)[-1]
        if not is_numeric_homba_id(local_id):
            break

        dhba_prefix = cfg.get("dhba_prefix", "")
        if dhba_prefix:
            tab.append(
                {
                    "ID": node_id,
                    "dhba_xref": dhba_prefix + local_id,
                    "atlas_link": "",
                    "atlas_link_label": "",
                    "prefLabel": "",
                }
            )

        for atlas in cfg.get("atlases", []):
            tab.append(
                {
                    "ID": node_id,
                    "dhba_xref": "",
                    "atlas_link": ATLAS_LINK.substitute(atlas_id=atlas["id"], structure_id=local_id),
                    "atlas_link_label": atlas.get("name", ""),
                    "prefLabel": "",
                }
            )
        break

with open(OUTPUT_PATH, "w", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=["ID", "dhba_xref", "atlas_link", "atlas_link_label", "prefLabel"],
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(tab)
