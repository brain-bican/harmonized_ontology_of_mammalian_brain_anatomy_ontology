import argparse
import json
from string import Template

import pandas as pd
from ruamel.yaml import YAML

parser = argparse.ArgumentParser(description="Generate HOMBA linkout template.")
parser.add_argument("filepath", help="Path to the json version of the ontology")
args = parser.parse_args()

with open(args.filepath, "r") as f:
    ontology_json = json.loads(f.read())

graph = ontology_json["graphs"][0]
with open("../config/db_graph_atlas.yaml", "r") as conf:
    mapping = YAML(typ="safe").load(conf.read()) or {}

link = Template("http://atlas.brain-map.org/atlas?atlas=$atlas_id#structure=$structure_id")

seed = {
    "ID": "ID",
    "xref": "A OboInOwl:hasDbXref",
    "prefLabel": "A skos:prefLabel",
}

tab = [seed]

for node in graph["nodes"]:
    if node.get("type") != "CLASS" or "lbl" not in node:
        continue

    matched = False
    for _, cfg in mapping.items():
        prefix = cfg.get("prefix")
        if prefix and str(node["id"]).startswith(prefix) and not str(node["id"]).endswith("_ENTITY"):
            atlases = cfg.get("atlases", [])
            if atlases:
                for atlas in atlases:
                    tab.append(
                        {
                            "ID": node["id"],
                            "xref": link.substitute(
                                atlas_id=atlas["id"],
                                structure_id=str(node["id"]).rsplit("_", 1)[-1],
                            ),
                            "prefLabel": "{} ({})".format(node["lbl"], cfg["species"]),
                        }
                    )
            else:
                tab.append({"ID": node["id"], "xref": "", "prefLabel": node["lbl"]})
            matched = True
            break

    if not matched:
        tab.append({"ID": node["id"], "xref": "", "prefLabel": node["lbl"]})

pd.DataFrame.from_records(tab).to_csv("../templates/linkouts.tsv", sep="\t", index=False)
