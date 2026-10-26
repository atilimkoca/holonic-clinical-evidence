"""llm_generator.py — SHACL-guided generation with iterative repair (§3.1).

Pipeline (Figure in the assignment §3.1):

    Transform(S) + grounded context  ->  prompt  ->  LLM  ->  Turtle
                                                              |
                          Project 2 validate_graph  <---------+
                                |                  fail (k<3) -> append violations
                                | pass             -> write results/generated_rdf/
                                v
                          GenerationResult (first-pass + per-iteration conformance)

The loop is provider-agnostic (default deterministic mock). Both RAG systems
reuse it; they differ only in the *initial* prompt + retrieved grounding, so the
loop is the controlled refinement budget shared by method (A) and baseline (B).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rdflib import Graph

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_REPO = _SRC.parents[1]
_P2_SRC = _REPO / "project_2_semantic" / "src"
if str(_P2_SRC) not in sys.path:
    sys.path.insert(0, str(_P2_SRC))

from namespaces import OE, OED, OEDRUG, OESRC, RDF_REIFIES, bind_all  # noqa: E402
from rdflib import Literal, URIRef                                    # noqa: E402
from rdflib.namespace import RDF, RDFS, XSD                            # noqa: E402
from shacl_to_prompt import ShapeTemplate, render_prompt              # noqa: E402
from llm_provider import LLMProvider, get_provider                    # noqa: E402

# Project 2's validator + loaders (the API contract).
from shacl_validator import load_ontology, load_shapes, validate_graph  # noqa: E402

_PROJ = _SRC.parent
GENERATED_DIR = _PROJ / "results" / "generated_rdf"
P2_SHAPES_A = _REPO / "project_2_semantic" / "shacl" / "shapes" / "boundary_aware"

DEFAULT_K = 3
MAX_GENERATION_TOKENS = 1024

# Prompt factor of the 2x2 ablation: which systems receive the SHACL-derived
# prompt skeleton + required-field guidance. The retrieval factor lives in
# graph_rag.SYSTEM_RETRIEVAL (A/C boundary-scoped, B/D naive top-k).
SHACL_GUIDED_SYSTEMS = ("A", "D")
BOUNDARY_SCOPED_SYSTEMS = ("A", "C")


@dataclass
class GenerationResult:
    holon_id: str
    system: str                                   # "A" | "B" | "C" | "D"
    passed: bool
    iterations: int
    per_iter_conforms: list = field(default_factory=list)
    per_iter_violations: list = field(default_factory=list)
    output_ttl: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def first_pass(self) -> bool:
        return bool(self.per_iter_conforms) and self.per_iter_conforms[0]

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# --------------------------------------------------------------------------- #
# Turtle extraction / parsing
# --------------------------------------------------------------------------- #

def extract_turtle(text: str) -> str:
    """Pull Turtle out of an LLM reply: strip ``` fences and leading prose."""
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        # take the longest fenced block, dropping a leading 'turtle' language tag
        blocks = [p[len("turtle"):] if p.lstrip().lower().startswith("turtle") else p
                  for p in parts[1::2]]
        if blocks:
            t = max(blocks, key=len)
    return t.strip()


def parse_turtle(text: str) -> Optional[Graph]:
    g = Graph()
    bind_all(g)
    try:
        g.parse(data=extract_turtle(text), format="turtle")
        return g
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Grounding context (typed entities so referential SHACL can run)
# --------------------------------------------------------------------------- #

def grounding_from_facts(facts: list) -> Graph:
    """Minimal typed-entity graph for the facts, so oe:cites/oe:treats resolve.

    In the full experiment the RAG layer supplies the real Project-1 subgraph;
    this keeps the generator runnable standalone and in tests.
    """
    g = Graph()
    bind_all(g)
    for f in facts:
        drug, dis, src = URIRef(f["s"]), URIRef(f["o"]), URIRef(f["source"])
        g.add((drug, RDF.type, OE.Drug))
        g.add((drug, RDFS.label, Literal(_local(drug), lang="en")))
        g.add((dis, RDF.type, OE.Disease))
        g.add((dis, RDFS.label, Literal(_local(dis), lang="en")))
        g.add((src, RDF.type, OE.EvidenceSource))
        g.add((src, RDFS.label, Literal(_local(src), lang="en")))
        g.add((src, OE.pubmedId, Literal(_local(src), datatype=XSD.string)))
    return g


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


# --------------------------------------------------------------------------- #
# Generation loop
# --------------------------------------------------------------------------- #

def _repair_block(violations: list) -> str:
    if not violations:
        return ""
    lines = ["\nFIX THESE SHACL VIOLATIONS (re-emit the full Turtle, corrected):"]
    seen = set()
    for v in violations:
        key = (v.get("path"), v.get("message"))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"  - {v.get('path','')}: {v.get('message','')}")
    return "\n".join(lines)


def _repair_fields(violations: list) -> list:
    """qname-ish paths to (re)require on the next mock iteration."""
    from shacl_to_prompt import qname
    out = []
    for v in violations:
        p = v.get("path")
        if p:
            try:
                out.append(qname(URIRef(p)))
            except Exception:
                pass
    return out


def generate(template: ShapeTemplate, context: dict, *, system: str,
             provider: Optional[LLMProvider] = None,
             grounding: Optional[Graph] = None,
             shapes_graph: Optional[Graph] = None,
             ont_graph: Optional[Graph] = None,
             k: int = DEFAULT_K, write: bool = False) -> GenerationResult:
    """Run the SHACL-guided generation loop for one holon under one system.

    `context` carries: holon_id, question, specialty, answer_text, facts,
    noise_facts. Systems A/D ship the SHACL `required_fields` + holon scaffold;
    systems B/C ship a naive prompt with no shape. The evidence each system
    sees is decided by its retrieval strategy (A/C boundary-scoped and
    noise-free, B/D the raw top-k union built by graph_rag).
    """
    provider = provider or get_provider()
    shapes_graph = shapes_graph if shapes_graph is not None else load_shapes(P2_SHAPES_A)
    ont_graph = ont_graph if ont_graph is not None else load_ontology()
    facts = context.get("facts", [])
    grounding = grounding if grounding is not None else grounding_from_facts(facts)

    shacl_guided = (system in SHACL_GUIDED_SYSTEMS)
    base_prompt = (render_prompt(template) if shacl_guided
                   else _naive_prompt(context))
    if shacl_guided:
        # Replace the generic subject in the SHACL-derived skeleton with the
        # actual evaluation resource. Leaving ``oegen:node_<id>`` in the prompt
        # makes instruction-following models copy an irrelevant placeholder.
        base_prompt = base_prompt.replace(
            "oegen:node_<id>", f"<{context.get('holon_uri', context.get('holon_id', 'g'))}>"
        )
    common_input = (_serialization_contract(context) + "\n\n"
                    + _retrieved_context_block(context, system))
    prompt = base_prompt + "\n\n" + common_input

    spec = {
        "task": "generate_rdf",
        "holon_id": context.get("holon_id", "g"),
        "holon_uri": context.get("holon_uri", str(context.get("holon_id", "g"))),
        "question": context.get("question", "?"),
        "answer_text": context.get("answer_text", "Generated answer."),
        "specialty": context.get("specialty", "General Medicine"),
        "facts": facts,
        "noise_facts": context.get("noise_facts", []),
        "emit_holon_scaffold": shacl_guided,
    }
    if shacl_guided:
        spec["required_fields"] = template.required_fields() + template.recommended_fields()

    per_conf, per_viol = [], []
    p_tok = c_tok = 0
    out_ttl = ""
    repair_fields: list = []
    for t in range(k):
        if repair_fields:
            spec = dict(spec, repair_fields=sorted(set(repair_fields)))
        resp = provider.complete(
            prompt, mock_spec=spec, temperature=0.0,
            max_tokens=MAX_GENERATION_TOKENS,
        )
        p_tok += resp.prompt_tokens
        c_tok += resp.completion_tokens
        out_ttl = resp.text
        gen = parse_turtle(out_ttl)
        if gen is None:                                  # unparseable -> hard fail
            per_conf.append(False)
            per_viol.append(99)
            prompt = base_prompt + "\n\n" + common_input + \
                "\n\nThe previous output was not valid Turtle. Re-emit valid Turtle only."
            continue
        data = gen + grounding
        conforms, _report, violations = validate_graph(
            data, shapes_graph, "sh:Violation", ont_graph=ont_graph)
        per_conf.append(conforms)
        per_viol.append(len(violations))
        if conforms:
            break
        repair_fields += _repair_fields(violations)
        prompt = (base_prompt + "\n\n" + common_input
                  + _repair_block(violations))

    res = GenerationResult(
        holon_id=context.get("holon_id", "g"), system=system,
        passed=bool(per_conf and per_conf[-1]),
        iterations=len(per_conf), per_iter_conforms=per_conf,
        per_iter_violations=per_viol, output_ttl=out_ttl,
        prompt_tokens=p_tok, completion_tokens=c_tok,
    )
    if write and res.passed:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        (GENERATED_DIR / f"{res.holon_id}_system{system}.ttl").write_text(out_ttl)
    return res


def _fact_lines(facts: list) -> list:
    lines = []
    for f in facts:
        lines.append(
            f"  - <{f['s']}> oe:treats <{f['o']}> "
            f"| confidence={f.get('confidence', 0.8):.2f} "
            f"| level={f.get('level', 'Level-1A')} "
            f"| source=<{f['source']}> "
            f"| effectiveness={f.get('effectiveness', 'effective')}"
        )
    return lines


def _retrieved_context_block(context: dict, system: str) -> str:
    """Render the evidence actually visible to each retrieval strategy.

    Boundary-scoped systems (A/C) expose only holon-admissible facts. Naive
    systems (B/D) receive the raw top-k union, with target and neighbouring
    facts deliberately unlabelled; otherwise a real provider would never see
    the over-retrieval represented by ``noise_facts`` and the comparison would
    not implement the stated baseline.
    """
    if system in BOUNDARY_SCOPED_SYSTEMS:
        header = "ADMISSIBLE EVIDENCE (use only these; do not invent facts):"
        visible = list(context.get("facts", []))
    else:
        header = ("RAW TOP-K RETRIEVED RDF FACTS (no relevance labels are "
                  "provided; answer the target question from this context):")
        visible = list(context.get("facts", [])) + list(context.get("noise_facts", []))
    return "\n".join([header] + _fact_lines(visible))


def _serialization_contract(context: dict) -> str:
    """Provider-independent syntax/identity contract shared by A and B.

    This supplies RDF namespace declarations and exact entity identifiers, not
    SHACL constraints. Therefore it removes an accidental mock-provider
    advantage without leaking System A's structural guidance to the baseline.
    """
    holon_uri = context.get(
        "holon_uri", "https://example.org/openevidence/questions/q_generated")
    return f"""COMMON RDF OUTPUT CONTRACT (identical for both systems):
- Return only syntactically valid Turtle; do not use Markdown fences or prose.
- Use the exact URIs supplied below; do not shorten, replace, or invent them.
- Use <{holon_uri}> as the subject of the clinical-question resource; do not
  create a substitute question/holon URI.
- Declare that resource as `<{holon_uri}> a holon:ClinicalQuestionHolon` so the
  same post-generation SHACL target is evaluated for both systems.
- Use these graph identifiers for that resource: <{holon_uri}-int> (interior),
  <{holon_uri}-bou> (boundary), <{holon_uri}-pro> (projection), and
  <{holon_uri}-con> (context).
- Include at least one retrieved relation that answers the target question.
  Emit its exact `<drug> oe:treats <disease> .` triple as a separate top-level
  Turtle statement. End the clinical-question property list with a period
  first; never place a complete triple after a semicolon. Do not wrap this
  relation in `oe:answer`, `oegen:answer`, `oe:hasFact`, or another property.
  Preserve the supplied URIs and do not replace `oe:treats` with another
  predicate.
- Include every prefix declaration that your output uses. Canonical prefixes:
  @prefix holon: <https://example.org/holon#> .
  @prefix oe: <https://example.org/openevidence#> .
  @prefix oeq: <https://example.org/openevidence/questions/> .
  @prefix oegen: <https://example.org/openevidence/generated/> .
  @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
  @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
  @prefix xsd: <http://www.w3.org/2001/XMLSchema#> ."""


def _naive_prompt(context: dict) -> str:
    """Naive prompt (systems B/C): raw triples, NO shape, NO structural guidance."""
    return (
        "Given the following RDF facts, generate Turtle that answers the "
        "question. No schema or shape constraints are provided.\n"
        f"Question: {context.get('question', '?')}\n"
    )


def main() -> None:
    """Standalone demo: one holon under System A vs System B."""
    facts = [{
        "s": str(OEDRUG.lisinopril), "o": str(OED.hypertension),
        "source": str(OESRC["34567890"]), "confidence": 0.95, "level": "Level-1A",
        "recorded": "2025-06-01", "effectiveness": "effective",
    }]
    ctx = {
        "holon_id": "demo_hypertension", "question": "First-line drug for hypertension?",
        "holon_uri": "https://example.org/openevidence/questions/q_demo",
        "specialty": "Cardiology", "answer_text": "Lisinopril is first-line.",
        "facts": facts, "noise_facts": [],
    }
    from shacl_to_prompt import load_shapes as load_shape_templates, node_shapes, transform
    sg = load_shape_templates(P2_SHAPES_A)
    cq = next(s for s in node_shapes(sg) if str(s).endswith("ClinicalQuestionShape"))
    template = transform(sg, cq)

    shapes = load_shapes(P2_SHAPES_A)
    ont = load_ontology()
    for system in ("A", "B"):
        r = generate(template, ctx, system=system, shapes_graph=shapes,
                     ont_graph=ont, write=False)
        print(f"System {system}: first_pass={r.first_pass} passed={r.passed} "
              f"iters={r.iterations} conf={r.per_iter_conforms} "
              f"viol={r.per_iter_violations} tokens={r.total_tokens}")


if __name__ == "__main__":
    main()
