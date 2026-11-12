"""
Clean architecture, checked on the imports of the whole project (2026-11-12). The dependencies point inward only:

    composition_root -> infrastructure -> application -> domain

and inside `application/` they go one way, from the outermost layer to the base (a cycle is a failure):

    service -> assembly, mappers -> runtime -> support -> ports, dtos -> domain

`domain/` imports nothing but the standard library, and `infrastructure/` imports it not at all: the inbound adapters use `dtos/inbound`, the
outbound ones `dtos/outbound` (the domain's own classes, exposed there), and what has to be converted is converted in `application/mappers/`. The ports hold only the abstract classes (the data they exchange is in `domain/`),
and the application opens no file and reads no environment variable itself: it is given them (`application/support/environment.py`).
"""
import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# application layer -> rank; an import may only go to the same or a lower rank
RANK = {"dtos": 0, "ports": 0, "support": 1, "runtime": 2, "assembly": 3, "mappers": 3, "service": 4}


def _python_files(folder):
    for base, dirs, files in os.walk(os.path.join(ROOT, folder)):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def _tree(path):
    with open(path, encoding="utf-8") as f:
        return ast.parse(f.read())


def _imports(path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name


def _rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def _only_ports_and_dtos(folder):
    bad = []
    for p in _python_files(folder):
        for m in _imports(p):
            parts = m.split(".")
            if parts[0] == "application" and not (len(parts) > 1 and parts[1] in ("ports", "dtos")):
                bad.append((_rel(p), m))
    return bad


def _application_imports_outside(folder, allowed):
    """(file, import) of every `application...` import under the folder that does not start with one of the allowed prefixes."""
    return [(_rel(p), m) for p in _python_files(folder) for m in _imports(p)
            if m.split(".")[0] == "application" and not m.startswith(allowed)]


class TestDependencyRule:
    def test_the_domain_imports_only_the_standard_library(self):
        bad = [(_rel(p), m) for p in _python_files("domain") for m in _imports(p)
               if m.split(".")[0] not in sys.stdlib_module_names and m.split(".")[0] != "domain"]
        assert bad == []

    def test_the_application_never_imports_infrastructure_or_the_composition_root(self):
        bad = [(_rel(p), m) for p in _python_files("application") for m in _imports(p)
               if m.split(".")[0] in ("infrastructure", "composition_root")]
        assert bad == []

    def test_infrastructure_never_imports_the_domain(self):
        bad = [(_rel(p), m) for p in _python_files("infrastructure") for m in _imports(p) if m.split(".")[0] == "domain"]
        assert bad == []

    def test_the_inbound_adapters_use_only_the_inbound_dtos_and_ports(self):
        assert _application_imports_outside("infrastructure/inbound", ("application.dtos.inbound", "application.ports.inbound")) == []

    def test_the_outbound_adapters_use_only_the_outbound_dtos_ports_and_mappers(self):
        allowed = ("application.dtos.outbound", "application.ports.outbound", "application.mappers.outbound")
        assert _application_imports_outside("infrastructure/outbound", allowed) == []

    def test_the_composition_root_may_use_everything(self):
        assert os.path.isfile(os.path.join(ROOT, "composition_root", "main.py"))

    def test_the_outbound_mappers_use_only_the_domain_and_the_dtos(self):
        assert _application_imports_outside("application/mappers/outbound", ("application.dtos", "application.mappers.outbound")) == []

    def test_the_inbound_mappers_use_only_the_dtos(self):
        assert _application_imports_outside("application/mappers/inbound", ("application.dtos", "application.mappers.inbound")) == []

    def test_the_outbound_dtos_are_the_domains_own_classes(self):
        for p in _python_files("application/dtos/outbound"):
            for node in ast.walk(_tree(p)):
                assert not isinstance(node, (ast.ClassDef, ast.FunctionDef)), _rel(p)

    def test_the_ports_use_only_the_domain_and_other_ports(self):
        assert _only_ports_and_dtos("application/ports") == []

    def test_an_outbound_port_never_uses_an_inbound_one(self):
        bad = [(_rel(p), m) for p in _python_files("application/ports/outbound") for m in _imports(p)
               if m.startswith("application.ports.inbound") or m.startswith("application.dtos.inbound")]
        assert bad == []

    def test_the_dtos_use_only_the_domain(self):
        bad = [(_rel(p), m) for p in _python_files("application/dtos") for m in _imports(p)
               if m.startswith("application.") and not m.startswith("application.dtos.")]
        assert bad == []


class TestOneWayInsideTheApplication:
    def test_no_layer_imports_one_above_it(self):
        bad = []
        for p in _python_files("application"):
            parts = _rel(p).split("/")
            if len(parts) < 3:
                continue
            mine = parts[1]
            for m in _imports(p):
                m_parts = m.split(".")
                if m_parts[0] != "application" or len(m_parts) < 2:
                    continue
                other = m_parts[1]
                if other in RANK and RANK[other] > RANK[mine]:
                    bad.append((_rel(p), m))
        assert bad == []

    def test_every_folder_of_the_application_has_a_rank(self):
        base = os.path.join(ROOT, "application")
        folders = {n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n)) and n != "__pycache__"}
        assert folders == set(RANK)


class TestNoInputOutputInTheApplication:
    # the one place that reaches the outside is application/support/environment.py, and it only calls the installed ports
    ALLOWED_LISTDIR = {"application/runtime/step/registry.py"}      # imports the Python step files of its own package

    def test_it_opens_no_file_and_reads_no_environment_variable(self):
        bad = []
        for p in _python_files("application"):
            for node in ast.walk(_tree(p)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                    bad.append((_rel(p), "open()"))
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                    if node.attr in ("environ", "getenv"):
                        bad.append((_rel(p), "os." + node.attr))
                    if node.attr in ("listdir", "walk", "scandir") and _rel(p) not in self.ALLOWED_LISTDIR:
                        bad.append((_rel(p), "os." + node.attr))
        assert bad == []
