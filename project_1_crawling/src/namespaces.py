"""Shared RDF namespaces, aligned with shared/ontology/prefixes.ttl.

Adds three project-local namespaces (specialties, symptoms, authors) that the
data layer needs but that are not in the shared prefix file.
"""
from __future__ import annotations

from rdflib import Namespace
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

PREFIXES = {
    "rdf": RDF, "rdfs": RDFS, "owl": OWL, "xsd": XSD, "prov": PROV,
    "holon": HOLON, "oe": OE, "oeq": OEQ, "oed": OED, "oedrug": OEDRUG,
    "oesrc": OESRC, "oeevt": OEEVT, "oespec": OESPEC, "oesym": OESYM,
    "oeauth": OEAUTH,
}


def bind_all(graph) -> None:
    """Bind every shared prefix on a graph/dataset for readable serialisation."""
    for pfx, ns in PREFIXES.items():
        graph.bind(pfx, ns)
