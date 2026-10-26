"""shacl_to_prompt.py — Transform(S): SHACL shape -> LLM prompt template (§3.1).

Implements the "SHACL as LLM MadLibs" idea: a SHACL NodeShape is parsed into an
explicit, constraint-annotated fill-in template that an LLM completes. The same
parse produces the machine-readable `required_fields` list the generator feeds
to the mock provider and uses to build repair prompts.

Formal companion: theory/transform_correctness.md (Transform definition,
correctness condition, k-iteration convergence).

CLI:
    python shacl_to_prompt.py            # writes prompts/templates/*.txt
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS, XSD

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from namespaces import PREFIXES, bind_all  # noqa: E402

SH = "http://www.w3.org/ns/shacl#"
_SH = lambda t: URIRef(SH + t)  # noqa: E731

_PROJ = _SRC.parent                                       # project_3_llm/
_REPO = _SRC.parents[1]                                    # social_network_final/
P2_SHAPES = _REPO / "project_2_semantic" / "shacl" / "shapes" / "boundary_aware"
TEMPLATE_DIR = _PROJ / "prompts" / "templates"

# Reverse prefix map (URI string -> prefix) for compact qnames in prompts.
# Includes the SHACL namespace so severities render as e.g. "sh:Violation"
# (the shared data-prefix map deliberately omits sh:).
_NS_ITEMS = sorted(
    [(str(ns), pfx) for pfx, ns in PREFIXES.items()] + [(SH, "sh")],
    key=lambda kv: -len(kv[0]))


def qname(term) -> str:
    """Render a URIRef as prefix:local using the shared prefix map."""
    s = str(term)
    for uri, pfx in _NS_ITEMS:
        if s.startswith(uri):
            return f"{pfx}:{s[len(uri):]}"
    return s


@dataclass
class PropertyConstraint:
    path: str                                # qname of sh:path
    datatype: Optional[str] = None           # qname of sh:datatype
    node_class: Optional[str] = None         # qname of sh:class
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    in_values: Optional[list] = None         # sh:in enumeration
    pattern: Optional[str] = None
    min_inclusive: Optional[float] = None
    max_inclusive: Optional[float] = None
    severity: str = "sh:Violation"
    message: str = ""

    @property
    def required(self) -> bool:
        """A field is 'required' (its omission is rejected) iff it is a
        Violation-severity constraint with minCount >= 1."""
        return self.severity == "sh:Violation" and (self.min_count or 0) >= 1


@dataclass
class ShapeTemplate:
    shape_uri: str
    target_class: Optional[str]
    properties: list = field(default_factory=list)
    or_groups: list = field(default_factory=list)        # list[list[str]] of paths

    def required_fields(self) -> list:
        return [p.path for p in self.properties if p.required]

    def recommended_fields(self) -> list:
        return [p.path for p in self.properties
                if not p.required and (p.min_count or 0) >= 1]


# --------------------------------------------------------------------------- #
# Parsing  (the Transform function, structural half)
# --------------------------------------------------------------------------- #

def _int(g: Graph, node, pred) -> Optional[int]:
    v = g.value(node, pred)
    return int(v) if v is not None else None


def _num(g: Graph, node, pred) -> Optional[float]:
    v = g.value(node, pred)
    return float(v) if v is not None else None


def _list(g: Graph, node, pred) -> Optional[list]:
    head = g.value(node, pred)
    if head is None:
        return None
    out = []
    for item in Collection(g, head):
        out.append(item.toPython() if isinstance(item, Literal) else qname(item))
    return out


def _parse_property(g: Graph, pshape) -> Optional[PropertyConstraint]:
    path = g.value(pshape, _SH("path"))
    if path is None:
        return None
    sev = g.value(pshape, _SH("severity"))
    dt = g.value(pshape, _SH("datatype"))
    cls = g.value(pshape, _SH("class"))
    return PropertyConstraint(
        path=qname(path),
        datatype=qname(dt) if dt is not None else None,
        node_class=qname(cls) if cls is not None else None,
        min_count=_int(g, pshape, _SH("minCount")),
        max_count=_int(g, pshape, _SH("maxCount")),
        in_values=_list(g, pshape, _SH("in")),
        pattern=(str(g.value(pshape, _SH("pattern")))
                 if g.value(pshape, _SH("pattern")) is not None else None),
        min_inclusive=_num(g, pshape, _SH("minInclusive")),
        max_inclusive=_num(g, pshape, _SH("maxInclusive")),
        severity=qname(sev) if sev is not None else "sh:Violation",
        message=str(g.value(pshape, _SH("message")) or ""),
    )


def transform(g: Graph, shape_uri: URIRef) -> ShapeTemplate:
    """Transform(S): parse one SHACL NodeShape into a ShapeTemplate.

    This is the structural core of Transform; `render_prompt` produces the
    natural-language artifact and `mock_spec_fields` the machine-readable view.
    """
    tc = g.value(shape_uri, _SH("targetClass"))
    props = []
    for pshape in g.objects(shape_uri, _SH("property")):
        pc = _parse_property(g, pshape)
        if pc is not None:
            props.append(pc)

    or_groups = []
    for orlist in g.objects(shape_uri, _SH("or")):
        group = []
        for alt in Collection(g, orlist):
            for ps in g.objects(alt, _SH("property")):
                p = g.value(ps, _SH("path"))
                if p is not None:
                    group.append(qname(p))
        if group:
            or_groups.append(group)

    # Deterministic ordering: required first, then by path name.
    props.sort(key=lambda p: (not p.required, p.path))
    return ShapeTemplate(
        shape_uri=qname(shape_uri),
        target_class=qname(tc) if tc is not None else None,
        properties=props,
        or_groups=or_groups,
    )


# --------------------------------------------------------------------------- #
# Rendering  (the Transform function, surface half)
# --------------------------------------------------------------------------- #

def _constraint_phrase(p: PropertyConstraint) -> str:
    bits = []
    if p.datatype:
        bits.append(f"datatype {p.datatype}")
    if p.node_class:
        bits.append(f"an instance of {p.node_class}")
    if p.in_values:
        vals = ", ".join(str(v) for v in p.in_values)
        bits.append(f"one of {{{vals}}}")
    if p.min_inclusive is not None or p.max_inclusive is not None:
        lo = p.min_inclusive if p.min_inclusive is not None else "-inf"
        hi = p.max_inclusive if p.max_inclusive is not None else "+inf"
        bits.append(f"in range [{lo}, {hi}]")
    if p.pattern:
        bits.append(f"matching /{p.pattern}/")
    card = []
    if p.min_count is not None:
        card.append(f"min {p.min_count}")
    if p.max_count is not None:
        card.append(f"max {p.max_count}")
    if card:
        bits.append("(" + ", ".join(card) + ")")
    return "; ".join(bits) if bits else "any value"


def _placeholder(p: PropertyConstraint) -> str:
    if p.in_values:
        return f'"<{"|".join(str(v) for v in p.in_values[:4])}{"|..." if len(p.in_values) > 4 else ""}>"'
    if p.datatype == "xsd:decimal":
        lo = p.min_inclusive if p.min_inclusive is not None else 0.0
        hi = p.max_inclusive if p.max_inclusive is not None else 1.0
        return f'"<{lo}-{hi}>"^^xsd:decimal'
    if p.datatype == "xsd:date":
        return '"<YYYY-MM-DD>"^^xsd:date'
    if p.datatype == "xsd:dateTime":
        return '"<YYYY-MM-DDThh:mm:ss>"^^xsd:dateTime'
    if p.datatype == "xsd:string":
        return '"<text>"^^xsd:string'
    if p.node_class:
        return f"<{p.node_class.split(':')[-1].lower()}-uri>"
    return "<value>"


PROMPT_HEADER = (
    "You are a careful biomedical knowledge engineer. Produce RDF 1.2 (Turtle) "
    "that is VALID against the SHACL shape below. Output ONLY Turtle (no prose). "
    "Use ONLY facts supplied in the ADMISSIBLE EVIDENCE block; never invent "
    "drugs, diseases, sources, dates, or numbers.\n"
)


def render_prompt(t: ShapeTemplate, *, with_header: bool = True) -> str:
    """Render the MadLibs prompt for a ShapeTemplate."""
    lines = []
    if with_header:
        lines.append(PROMPT_HEADER)
    lines.append(f"# SHACL TARGET: {t.shape_uri}"
                 + (f"  (target class {t.target_class})" if t.target_class else ""))
    req = [p for p in t.properties if p.required]
    rec = [p for p in t.properties if not p.required]
    if req:
        lines.append("\nREQUIRED fields (omission => the output is REJECTED):")
        for p in req:
            lines.append(f"  - {p.path}: {_constraint_phrase(p)}")
    if rec:
        lines.append("\nRECOMMENDED fields (warnings if missing):")
        for p in rec:
            lines.append(f"  - {p.path}: {_constraint_phrase(p)}")
    for grp in t.or_groups:
        lines.append(f"\nAt least one of: {', '.join(grp)} (sh:or).")
    # The fill-in skeleton.
    lines.append("\nFILL THIS TEMPLATE (replace every <...>):")
    subj = "oegen:ev_<id>" if (t.target_class or "").endswith("EvidenceAssertion") \
        else "oegen:node_<id>"
    skeleton = [f"{subj} a {t.target_class} ;" if t.target_class else f"{subj}"]
    body = req + rec
    for i, p in enumerate(body):
        term = ";" if i < len(body) - 1 else "."
        skeleton.append(f"    {p.path} {_placeholder(p)} {term}")
    lines.append("\n".join(skeleton))
    return "\n".join(lines) + "\n"


def mock_spec_fields(t: ShapeTemplate) -> dict:
    """Machine-readable view used by the generator + mock provider."""
    return {
        "shape": t.shape_uri,
        "target_class": t.target_class,
        "required_fields": t.required_fields(),
        "recommended_fields": t.recommended_fields(),
    }


# --------------------------------------------------------------------------- #
# Convenience loaders
# --------------------------------------------------------------------------- #

def load_shapes(path: Path = P2_SHAPES) -> Graph:
    g = Graph()
    bind_all(g)
    files = sorted(path.glob("**/*.ttl")) if path.is_dir() else [path]
    for f in files:
        g.parse(f, format="turtle")
    return g


def node_shapes(g: Graph) -> list:
    """All named (URIRef) node shapes in a shapes graph, deterministically sorted."""
    out = set()
    for s in g.subjects(RDF.type, _SH("NodeShape")):
        if isinstance(s, URIRef):
            out.add(s)
    # also include subjects that carry sh:property even without explicit type
    for s in g.subjects(_SH("property"), None):
        if isinstance(s, URIRef):
            out.add(s)
    return sorted(out, key=str)


def main() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    g = load_shapes()
    shapes = node_shapes(g)
    written = 0
    for su in shapes:
        t = transform(g, su)
        if not t.properties:
            continue
        fname = qname(su).replace(":", "_") + ".txt"
        (TEMPLATE_DIR / fname).write_text(render_prompt(t))
        written += 1
    print(f"Transform(S): {written} shape templates written to {TEMPLATE_DIR}")
    # Show the evidence reifier template (the main generation target).
    for su in shapes:
        if str(su).endswith("EvidenceReifierShape"):
            t = transform(g, su)
            print("\n--- EvidenceReifierShape -> prompt ---")
            print(render_prompt(t, with_header=False))
            print("required_fields =", t.required_fields())
            break


if __name__ == "__main__":
    main()
