"""
Smoke + behaviour tests for the Project 2 detection experiment.

Run from the project_2_semantic directory:
    ../.venv/bin/python -m pytest tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJ / "src"))

from corpus_generator import INJECTORS, build_consistent          # noqa: E402
from shacl_validator import detect, load_ontology, load_shapes     # noqa: E402

SET_A = _PROJ / "shacl" / "shapes" / "boundary_aware"
SET_B = _PROJ / "shacl" / "shapes" / "flat"


@pytest.fixture(scope="module")
def engine():
    return load_ontology(), load_shapes(SET_A), load_shapes(SET_B)


def test_consistent_holon_passes_both(engine):
    ont, a, b = engine
    g = build_consistent(7)
    assert detect(g, a, ont)[0] is False, "Set A false-positives on a clean holon"
    assert detect(g, b, ont)[0] is False, "Set B false-positives on a clean holon"


@pytest.mark.parametrize("t", ["T1", "T2", "T3"])
def test_structural_defects_caught_by_both(engine, t):
    ont, a, b = engine
    g, _ = INJECTORS[t](500)
    assert detect(g, a, ont)[0] is True, f"Set A missed {t}"
    assert detect(g, b, ont)[0] is True, f"Set B missed {t}"


@pytest.mark.parametrize("t", ["T4", "T5", "T6"])
def test_semantic_defects_only_caught_by_boundary_aware(engine, t):
    ont, a, b = engine
    g, _ = INJECTORS[t](600)
    assert detect(g, a, ont)[0] is True, f"Set A (boundary-aware) missed {t}"
    assert detect(g, b, ont)[0] is False, f"Set B (flat) unexpectedly caught {t}"
