import argparse
import logging
import os
import urllib.request

from relation_validator import read_csv_to_dict
from structure_graph_utils import read_structure_graph
from abc import ABC, abstractmethod, ABCMeta

MAPPING_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../templates/homba_CCF_to_UBERON.tsv")
PATH_REPORT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../validation_report.txt")
STRUCTURE_GRAPH_URL = "https://allen-hmba-releases.s3.us-west-2.amazonaws.com/terminology/HOMBA_v1.json"
STRUCTURE_GRAPH_FILE = "HOMBA_v1.json"

log = logging.getLogger(__name__)


def save_report(report):
    with open(PATH_REPORT, "w") as f:
        for rep in report:
            f.write(rep + "\n")


class BaseChecker(ABC):

    @abstractmethod
    def check(self):
        pass

    @abstractmethod
    def get_header(self):
        return "=== Default Checker :"


class StrictChecker(BaseChecker, metaclass=ABCMeta):
    pass


class SoftChecker(BaseChecker, metaclass=ABCMeta):
    pass


class SingleMappingChecker(StrictChecker):
    def __init__(self):
        self.reports = []

    def check(self):
        headers, records = read_csv_to_dict(MAPPING_FILE, delimiter="\t", generated_ids=True)
        for mapping in records:
            if records[mapping]["Equivalent"] and records[mapping]["Subclass part of"] and records[mapping]["ID"] != "ID":
                self.reports.append("{} has both Equivalent and SubClassOf".format(records[mapping]["ID"]))

    def get_header(self):
        return "=== Single Mapping Checks :"


class UniqueIdChecker(StrictChecker):
    def __init__(self):
        self.reports = []

    def check(self):
        headers, records = read_csv_to_dict(MAPPING_FILE, delimiter="\t", generated_ids=True)
        id_mapping = {}
        for line_number in records:
            mapped_id = records[line_number]["ID"]
            record = {
                "line": line_number + 1,
                "sc": records[line_number]["Subclass part of"],
                "ec": records[line_number]["Equivalent"],
            }
            id_mapping.setdefault(mapped_id, []).append(record)

        for mapping_id, rows in id_mapping.items():
            if len(rows) > 1:
                base_record = rows[0]
                all_same = all(base_record["sc"] == row["sc"] and base_record["ec"] == row["ec"] for row in rows[1:])
                if not all_same:
                    self.reports.append(
                        "{} exists in multiple lines: {} with different mappings.".format(
                            mapping_id, ", ".join(str(record["line"]) for record in rows)
                        )
                    )

    def get_header(self):
        return "=== Unique Id Checks :"


class StructureGraphChecker(StrictChecker):
    def __init__(self):
        self.reports = []

    def check(self):
        urllib.request.urlretrieve(STRUCTURE_GRAPH_URL, STRUCTURE_GRAPH_FILE)
        structure_graph_list = read_structure_graph(STRUCTURE_GRAPH_FILE)
        structure_graph = {item["id"]: item for item in structure_graph_list}

        headers, records = read_csv_to_dict(MAPPING_FILE, delimiter="\t", generated_ids=True)
        for line_number in records:
            mapped_id = str(records[line_number]["ID"]).strip()
            if mapped_id and mapped_id != "ID" and not str(mapped_id).endswith("HOMBA_ENTITY"):
                if mapped_id not in structure_graph:
                    self.reports.append("{} not exists in the structure graph.".format(mapped_id))

        for line_number in records:
            mapped_id = records[line_number]["ID"]
            if mapped_id in structure_graph:
                label = str(records[line_number]["Label"]).lower().strip()
                expected = str(structure_graph[mapped_id]["name"]).lower().strip()
                if expected != label:
                    self.reports.append(
                        "{} label is '{}' in template, but '{}' in the structure graph.".format(
                            mapped_id, records[line_number]["Label"], structure_graph[mapped_id]["name"]
                        )
                    )

    def get_header(self):
        return "=== Structure Graph Compatibility :"


class MappingValidator(object):
    rules = [SingleMappingChecker(), UniqueIdChecker(), StructureGraphChecker()]
    errors = []
    warnings = []

    def validate(self):
        for checker in self.rules:
            checker.check()
            if checker.reports:
                if isinstance(checker, StrictChecker):
                    self.errors.append("\n" + checker.get_header())
                    self.errors.extend(checker.reports)
                else:
                    self.warnings.append("\n" + checker.get_header())
                    self.warnings.extend(checker.reports)


class ValidationError(Exception):
    def __init__(self, message, report):
        Exception.__init__(self)
        self.message = message
        self.report = report


def main(silent):
    log.info("Mapping validation started.")
    validator = MappingValidator()
    validator.validate()
    if not validator.errors and not validator.warnings:
        print("\nMarker validation successful.")
    elif not validator.errors:
        print("Warnings:")
        for rep in validator.warnings:
            print(rep)
        print("\nMarker validation completed with warnings.")
    else:
        print("\nErrors:")
        for rep in validator.errors:
            print(rep)
        if validator.warnings:
            print("\nWarnings:")
            for rep in validator.warnings:
                print(rep)
        print("\nMarker validation completed with errors.")
        if not silent:
            raise ValidationError("Marker validation completed with errors.", validator.errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", action="store_true")
    args = parser.parse_args()
    main(args.silent)
