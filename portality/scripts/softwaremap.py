import re
import csv
import os

INCLUDE = ["*.py", "*.html"]
DELIMIT = "~~"
RX = "~~(.+)~~"

class MapException(Exception):
    def __init__(self, message, file=None, line=None):
        self.message = message
        self.file = file
        self.line = line
        super(MapException, self).__init__()

    def __str__(self):
        ref = ""
        if self.file is not None:
            ref = self.file
            if self.line is not None:
                ref += "#L" + str(self.line)
        return "{msg} {ref}".format(msg=self.message, ref=ref)

class Analysis(object):
    def __init__(self):
        self._relations = {}
        self._files = {}
        self._entities = {}
        self._targets = set()
        self._terminals = []

    @property
    def relations(self):
        return self._relations

    @property
    def files(self):
        return self._files

    @property
    def entities(self):
        return self._entities

    @property
    def no_downstreams(self):
        return [t for t in self._targets if t not in self._relations and t not in self._terminals]

    @property
    def unexpected_downstreams(self):
        return [t for t in self._terminals if t in self._relations]

    @property
    def unseen_terminals(self):
        return [t for t in self._terminals if t not in self._targets]

    @property
    def terminals(self):
        return self._terminals

    @terminals.setter
    def terminals(self, val):
        self._terminals = val

    def add_known_target(self, target):
        self._targets.add(target)

    def add_entity_definition(self, name, file, line):
        if name not in self._entities:
            self._entities[name] = []
        self._entities[name].append({
            "file" : file,
            "line" : line
        })
        self.add_known_target(name)

    def add_relation(self, name):
        if name not in self._relations:
            self._relations[name] = Relation(self, name)
        self.add_known_target(name)
        return self._relations[name]

    def add_file(self, filename):
        if filename not in self._files:
            self._files[filename] = 0

    def annotation_hit(self, filename):
        self.add_file(filename)
        self._files[filename] += 1


class Relation(object):
    def __init__(self, analysis, name=None):
        self.analysis = analysis
        self.name = name
        self.refs = {}

    def add_ref(self, rel, target, file, line):
        if rel not in self.refs:
            self.refs[rel] = {}
        if target not in self.refs[rel]:
            self.refs[rel][target] = []
        self.refs[rel][target].append({
            "file": file,
            "line": line
        })
        self.analysis.add_known_target(target)


def parse_tree(directory, analysis, valid_types, type_validation):
    for root, dirs, files in os.walk(directory):
        for name in files:
            parse_file(os.path.join(root, name), analysis, valid_types, type_validation)


def parse_file(file, analysis, valid_types, type_validation):
    analysis.add_file(file)
    with open(file, "r") as f:
        context = False
        ln = 0
        for line in f:
            ln += 1
            if DELIMIT in line:
                m = re.findall(RX, line)
                if not m:
                    continue
                for annotation in m:
                    analysis.annotation_hit(file)

                    try:
                        ref = parse_reference(annotation)
                    except MapException as e:
                        e.file = f.name
                        e.line = ln
                        raise

                    if ref.get("switch_context", True):
                        if "context" in ref:
                            context = ref["context"]

                            try:
                                validate_entity(context, valid_types, type_validation)
                            except MapException as e:
                                e.file = f.name
                                e.line = ln
                                raise

                            analysis.add_entity_definition(context, f.name, ln)
                        if not context:
                            raise MapException("Context not set when annotation provided", f.name, ln)
                        if "rel" in ref:
                            try:
                                validate_entity(ref["target"], valid_types, type_validation)
                            except MapException as e:
                                e.file = f.name
                                e.line = ln
                                raise
                            relation = analysis.add_relation(context)
                            relation.add_ref(ref["rel"], ref["target"], f.name, ln)
                    else:
                        analysis.add_entity_definition(ref["context"], f.name, ln)
                        relation = analysis.add_relation(ref["context"])
                        relation.add_ref(ref["rel"], ref["target"], f.name, ln)


def validate_entity(entity, valid_types, type_validation):
    if type_validation == "none":
        return True
    type = entity.split(":")[1]
    if type in valid_types:
        return True
    if type_validation == "error":
        raise MapException("Type '{x}' is not an allowed type".format(x=type))


def parse_reference(text):
    bits = [x.strip() for x in text.strip().split(" ")]
    if len(bits) == 1:
        return {"context" : bits[0]}
    if len(bits) == 2:
        return {"rel" : bits[0], "target" : bits[1]}
    if len(bits) == 3:
        return {"switch_context" : True, "context" : bits[0], "rel" : bits[1], "target" : bits[2]}
    if len(bits) == 4 and bits[0] == "!":
        return {"switch_context" : False, "context" : bits[1], "rel" : bits[2], "target" : bits[3]}
    raise MapException("Unable to parse text '{x}'".format(x=text))


def data2csv(data, out):
    if not os.path.exists(out):
        os.makedirs(out)

    relationships = os.path.join(out, "relationships.csv")
    with open(relationships, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        for k, relation in data.relations.items():
            for rel, targets in relation.refs.items():
                for target, occurrences in targets.items():
                    refs = "; ".join([o["file"] + "#L" + str(o["line"]) for o in occurrences])
                    writer.writerow([k, rel, target, refs])

    filelist = os.path.join(out, "files.csv")
    with open(filelist, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        writer.writerow(["File Path", "Annotation Count"])
        for k, v in data.files.items():
            writer.writerow([k, v])

    entities = os.path.join(out, "entities.csv")
    with open(entities, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        for k, v in data.entities.items():
            refs = "; ".join([o["file"] + "#L" + str(o["line"]) for o in v])
            writer.writerow([k, refs])

    no_downstream = os.path.join(out, "no-downstream.csv")
    with open(no_downstream, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        for target in data.no_downstreams:
            writer.writerow([target])

    unexpected_downstram = os.path.join(out, "unexpected-downstream.csv")
    with open(unexpected_downstram, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        for target in data.unexpected_downstreams:
            writer.writerow([target])

    unseen_terminals = os.path.join(out, "unseen-terminals.csv")
    with open(unseen_terminals, "w", encoding="utf-8") as o:
        writer = csv.writer(o)
        for target in data.unseen_terminals:
            writer.writerow([target])


def run(source, target, type_source=None, type_validation="none", terminals_source=None):
    try:
        valid_types = []
        if type_source is not None:
            with open(type_source, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                valid_types = [row[0] for row in reader]

        terminal_entities = []
        if terminals_source is not None:
            with open(terminals_source, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                terminal_entities = [row[0] for row in reader]

        data = Analysis()
        data.terminals = terminal_entities

        parse_tree(source, data, valid_types, type_validation)
        data2csv(data, target)
    except MapException as e:
        print(str(e))

def test():
    run("/home/richard/Code/External/doaj3/portality/templates/",
         "/home/richard/tmp/doaj/softwaremap",
        "/home/richard/Code/External/doaj3/softwaremap/types.csv",
        "error",
        "/home/richard/Code/External/doaj3/softwaremap/terminals.csv")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="File to parse")
    parser.add_argument("-o", "--out", help="Output Directory")
    parser.add_argument("-t", "--types", help="Types registru")
    args = parser.parse_args()

    run(args.file, args.out, args.types)

