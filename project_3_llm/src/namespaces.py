"""Shared RDF namespaces for Project 3, aligned with shared/ontology/prefixes.ttl
and identical to Project 1's `namespaces.py` so the layers interoperate.

Adds `RDF_REIFIES` (the RDF 1.2 term rdflib's closed namespace does not expose)
and `OEGEN` for LLM-generated answer / assertion nodes.
"""
from __future__ import annotations

from rdflib import Namespace, URIRef
from rdflib.namespace import OWL, PROV, RDF, RDFS, XSD

HOLON = Namespace("https://example.org/holon#")
OE = Namespace("https://example.org/openevidence#")
OEQ = Namespace("https://example.org/openevidence/questions/")
OED = Namespace("https://example.org/openevidence/diseases/")
OEDRUG = Namespace("https://example.org/openevidence/drugs/")
OESRC = Namespace("https://example.org/openevidence/sources/")
OEEVT = Namespace("https://example.org/openevidence/events/")
OESPEC = Namespace("https://example.org/openevidence/specialties/")
OESYM = Namespace("https://example.org/openevidence/symptoms/")
OEAUTH = Namespace("https://example.org/openevidence/authors/")
OEGEN = Namespace("https://example.org/openevidence/generated/")

# RDF 1.2 triple-term reification predicate (materialised pattern; see Project 1/2).
RDF_REIFIES = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")

PREFIXES = {
    "rdf": RDF, "rdfs": RDFS, "owl": OWL, "xsd": XSD, "prov": PROV,
    "holon": HOLON, "oe": OE, "oeq": OEQ, "oed": OED, "oedrug": OEDRUG,
    "oesrc": OESRC, "oeevt": OEEVT, "oespec": OESPEC, "oesym": OESYM,
    "oeauth": OEAUTH, "oegen": OEGEN,
}

# SPARQL prefix block, reusable by the query / governance modules.
SPARQL_PREFIXES = "\n".join(
    f"PREFIX {pfx}: <{ns}>" for pfx, ns in PREFIXES.items()
)


def bind_all(graph) -> None:
    """Bind every shared prefix on a graph/dataset for readable serialisation."""
    for pfx, ns in PREFIXES.items():
        graph.bind(pfx, ns)
