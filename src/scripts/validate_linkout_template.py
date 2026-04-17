import argparse
import csv
from collections import defaultdict
from pathlib import Path


def is_numeric_homba_id(local_id):
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


parser = argparse.ArgumentParser(description="Validate generated HOMBA linkout template rows.")
parser.add_argument("template", help="Path to linkouts.tsv")
parser.add_argument(
    "--config",
    default=str(Path(__file__).resolve().parent.parent / "config" / "db_graph_atlas.yaml"),
    help="Path to db_graph_atlas.yaml",
)
args = parser.parse_args()

config = load_simple_yaml(Path(args.config))
homba_cfg = config.get("homba", {})
homba_prefix = homba_cfg.get("prefix", "")
dhba_prefix = homba_cfg.get("dhba_prefix", "")
atlas_ids = [str(atlas["id"]) for atlas in homba_cfg.get("atlases", [])]
atlas_names = [atlas.get("name", "") for atlas in homba_cfg.get("atlases", [])]
expected_atlas_count = len(atlas_ids)

stats = defaultdict(lambda: {"dhba_xrefs": [], "atlas_links": [], "atlas_link_labels": []})

with open(args.template, "r", newline="") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    for row in reader:
        node_id = row["ID"]
        if node_id == "ID" or not node_id.startswith(homba_prefix):
            continue

        stats[node_id]
        local_id = node_id.rsplit("_", 1)[-1]
        if row["dhba_xref"]:
            stats[node_id]["dhba_xrefs"].append(row["dhba_xref"])
        if row["atlas_link"]:
            stats[node_id]["atlas_links"].append(row["atlas_link"])
            stats[node_id]["atlas_link_labels"].append(row.get("atlas_link_label", ""))

        if not is_numeric_homba_id(local_id):
            if row["dhba_xref"]:
                raise ValueError(f"AA HOMBA term unexpectedly received a DHBA xref: {node_id}")
            if row["atlas_link"]:
                raise ValueError(f"AA HOMBA term unexpectedly received an atlas link: {node_id}")
            if row.get("atlas_link_label"):
                raise ValueError(f"AA HOMBA term unexpectedly received an atlas link label: {node_id}")

for node_id, values in stats.items():
    local_id = node_id.rsplit("_", 1)[-1]
    if not is_numeric_homba_id(local_id):
        continue

    expected_dhba = dhba_prefix + local_id
    if values["dhba_xrefs"] != [expected_dhba]:
        raise ValueError(
            f"{node_id} should have exactly one DHBA xref {expected_dhba}, found {values['dhba_xrefs']}"
        )

    expected_links = [
        f"http://atlas.brain-map.org/atlas?atlas={atlas_id}#structure={local_id}"
        for atlas_id in atlas_ids
    ]
    if values["atlas_links"] != expected_links:
        raise ValueError(
            f"{node_id} should have {expected_atlas_count} atlas links {expected_links}, "
            f"found {values['atlas_links']}"
        )
    if values["atlas_link_labels"] != atlas_names:
        raise ValueError(
            f"{node_id} should have atlas link labels {atlas_names}, "
            f"found {values['atlas_link_labels']}"
        )

print(
    f"Validated HOMBA linkouts for {len(stats)} HOMBA classes; "
    f"numeric terms carry one DHBA xref and {expected_atlas_count} labeled atlas links."
)
