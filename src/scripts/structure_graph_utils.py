import json
import ntpath


NAMESPACES = {
    "HOMBA_v1.json": "https://purl.brain-bican.org/ontology/HOMBA_",
}


def _curie_to_iri(curie, namespace):
    local_id = str(curie).split(":", 1)[-1]
    return namespace + local_id


def read_structure_graph(graph_json):
    with open(graph_json, "r") as f:
        payload = json.loads(f.read())

    data_list = []
    namespace = NAMESPACES[ntpath.basename(graph_json)]

    if isinstance(payload, dict) and "msg" in payload:
        for root in payload["msg"]:
            tree_recurse_allen(root, data_list, namespace)
    else:
        tree_recurse_homba(payload, data_list, namespace)

    return data_list


def tree_recurse_allen(node, dl, namespace):
    d = {
        "id": namespace + str(node["id"]),
        "name": str(node["name"]).strip(),
        "acronym": node["acronym"],
        "symbol": node["acronym"],
    }
    if d["name"] == "root":
        d["name"] = "brain"
    if node["parent_structure_id"]:
        d["parent_structure_id"] = namespace + str(node["parent_structure_id"])
    dl.append(d)

    for child in node["children"]:
        tree_recurse_allen(child, dl, namespace)


def tree_recurse_homba(node, dl, namespace, parent_iri=None):
    if "HOMBA_id" not in node or "name" not in node:
        raise ValueError("Each HOMBA node must contain HOMBA_id and name")

    iri = _curie_to_iri(node["HOMBA_id"], namespace)
    acronym = node.get("acronym", "")
    d = {
        "id": iri,
        "name": str(node["name"]).strip(),
        "acronym": acronym,
        "symbol": acronym,
    }
    if parent_iri:
        d["parent_structure_id"] = parent_iri
    dl.append(d)

    for child in node.get("children", []):
        tree_recurse_homba(child, dl, namespace, iri)
