import re
import csv
import os
from lark import Lark
from jinja2 import Environment
import json
import fnmatch


INCLUDE = ["*.py", "*.html"]
DELIMIT = "~~"
RX = "~~(.+)~~"
PARSER = Lark("""
start: context
     | link entity
     | context link entity
     | noswitch context link entity

context: CONTEXT -> context
link: LINK -> link
entity: ENTITY -> entity
noswitch: NOSWITCH -> noswitch

CONTEXT: PREFIX ":" TYPE
LINK: " "* "->" " "* 
    | " "+ SYMBOL " "+
ENTITY: PREFIX ":" TYPE
NOSWITCH: " "* "!" " "*

PREFIX: SYMBOL
TYPE: SYMBOL

LOWER: ("a".."z")+
UPPER: ("A".."Z")+
NUMBER: ("0".."9")+
SYMBOL: (LOWER | UPPER | NUMBER)+
""")

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

    @property
    def ordered_triples(self):
        subjects = list(self._targets)
        subjects.sort()

        triples = []
        for s in subjects:
            relations = self._relations.get(s)
            if relations:
                relation_triples = relations.ordered_triples
                triples += relation_triples

            for _, r in self._relations.items():
                if s in r.targets:
                    triples += r.triples_for(s)

        return triples

    def entity_definitions(self, entity_name):
        return self._entities.get(entity_name, "")

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
        self.targets = []

    def add_ref(self, rel, target, file, line):
        if rel not in self.refs:
            self.refs[rel] = {}
        if target not in self.refs[rel]:
            self.refs[rel][target] = []
        self.refs[rel][target].append({
            "file": file,
            "line": line
        })
        self.targets.append(target)
        self.analysis.add_known_target(target)

    @property
    def ordered_triples(self):
        refs = list(self.refs.keys())
        refs.sort()

        triples = []
        for r in refs:
            objects = list(self.refs[r].keys())
            objects.sort()
            for o in objects:
                triples.append((self.name, r, o, self.refs[r][o]))

        return triples

    def triples_for(self, o):
        refs = list(self.refs.keys())
        refs.sort()

        triples = []
        for r in refs:
            if o not in self.refs[r]:
                continue
            triples.append((o, self._reverse(r), self.name, self.refs[r][o]))

        return triples

    def _reverse(self, rel):
        if rel == "->":
            return "<-"
        return "<- " + rel

def parse_tree(config, analysis):#directory, analysis, valid_types, type_validation):
    directory = config.get("dir")
    exclude_dirs = config.get("exclude_dirs", [])
    exclude_files = config.get("exclude_files", [])

    for root, dirs, files in os.walk(directory):
        skip = False
        for ed in exclude_dirs:
            if root.startswith(ed):
                skip = True
        if skip:
            continue
        for name in files:
            skip = False
            for ef in exclude_files:
                if fnmatch.fnmatch(name, ef):
                    skip = True
            if skip:
                continue
            path = os.path.join(root, name)
            parse_file(config, path, analysis)#, valid_types, type_validation)


def parse_file(config, file, analysis):#, valid_types, type_validation):
    valid_types = config.get("valid_types", [])
    type_validation = config.get("type_validation", "none")
    ignore_parse_errors = file in config.get("ignore_parse_errors_in", [])

    analysis.add_file(file)
    with open(file, "r") as f:
        context = False
        ln = 0
        try:
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
                            if ignore_parse_errors:
                                continue
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
        except UnicodeDecodeError as e:
            print("UnicodeDecodeError on file {f}".format(f=file))


def validate_entity(entity, valid_types, type_validation):
    if type_validation == "none":
        return True
    type = entity.split(":")[1]
    if type in valid_types:
        return True
    if type_validation == "error":
        raise MapException("Type '{x}' is not an allowed type".format(x=type))


def parse_reference(text):
    try:
        tree = PARSER.parse(text.strip())
    except:
        raise MapException("Unable to parse text '{x}'".format(x=text))

    resp = {}
    for child in tree.children:
        field_name = child.data
        field_value = child.children[0].value.strip()

        if field_name == "noswitch":
            resp["switch_context"] = False
        if field_name == "context":
            resp["context"] = field_value
        if field_name == "link":
            resp["rel"] = field_value
        if field_name == "entity":
            resp["target"] = field_value
    return resp


def data2csv(config, data):#, out):
    out = config.get("out")
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


def data2json():
    pass


def data2html(config, data):#, out, html_template):
    out = config.get("out")
    html_template = config.get("html_template")

    if not os.path.exists(out):
        os.makedirs(out)

    env = Environment()
    with open(html_template, "r", encoding="utf-8") as f:
        template = env.from_string(f.read())

    page = template.render(data=data)

    outfile = os.path.join(out, "html", "index.html")
    outdir = os.path.dirname(outfile)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(page)


def run(config):#source, target, type_source=None, type_validation="none", terminals_source=None, html_template=None):

    type_source = config.get("types")
    terminals_source = config.get("terminals")

    try:
        valid_types = []
        if type_source is not None:
            with open(type_source, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                valid_types = [row[0] for row in reader]
        config["valid_types"] = valid_types

        terminal_entities = []
        if terminals_source is not None:
            with open(terminals_source, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                terminal_entities = [row[0] for row in reader]

        data = Analysis()
        data.terminals = terminal_entities

        parse_tree(config, data)#source, data, valid_types, type_validation)
        data2csv(config, data)#, target)
        if "html_template" in config:
            data2html(config, data)#, target, html_template)
    except MapException as e:
        print(str(e))


def test():
    with open("/home/richard/Code/External/doaj3/softwaremap/config.json", "r", encoding="utf-8") as f:
        config = json.loads(f.read())
    run(config)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="config file")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.loads(f.read())
    run(config)

