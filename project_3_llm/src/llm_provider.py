"""llm_provider.py — pluggable LLM backend with an offline response cache.

Design (mirrors Project 1's cached-PubMed philosophy):

* **Default = deterministic Mock.** No network, no secrets, fully reproducible.
  The mock is a *prompt-driven simulator*: its output is a pure function of the
  structured `mock_spec` the caller passes. System A and System B differ ONLY in
  the spec they build (A ships SHACL `required_fields`, confidence-filtered,
  projection-only facts; B ships more, noisier, unconstrained facts), so the
  A-vs-B comparison faithfully reflects the *retrieval/prompting design under
  test* rather than any hard-coded verdict. (See README "Threats to Validity".)

* **Real providers** (OpenAI / Anthropic / Ollama) activate via env vars:
      P3_LLM_PROVIDER = mock | openai | anthropic | ollama
      P3_LLM_MODEL    = <model name>          (provider-specific default otherwise)
      OPENAI_API_KEY / ANTHROPIC_API_KEY      (for the hosted providers)
  Every completion is cached on disk keyed by (provider, model, temperature,
  system, prompt) so that once a real response is obtained the whole pipeline
  replays offline and deterministically.

Public API:
    provider = get_provider()                      # from env, defaults to mock
    resp = provider.complete(prompt, system=..., mock_spec=...)
    resp.text, resp.total_tokens, resp.cached
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

_THIS = Path(__file__).resolve()
_PROJ = _THIS.parents[1]                       # project_3_llm/
DEFAULT_CACHE = _PROJ / "data" / "llm_cache"

# OpenEvidence vocabulary URIs the mock emits (kept in sync with the ontology).
_HOLON = "https://example.org/holon#"
_OE = "https://example.org/openevidence#"
_OEQ = "https://example.org/openevidence/questions/"
_OEGEN = "https://example.org/openevidence/generated/"
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_XSD = "http://www.w3.org/2001/XMLSchema#"


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token), used for the mock
    and as a fallback when a real provider does not return usage."""
    return max(1, len(text) // 4)


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached: bool = False
    iterations: int = 1                 # filled by callers that loop
    meta: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

def _cache_key(provider: str, model: str, temperature: float, max_tokens: int,
               system: Optional[str], prompt: str, spec_sig: str) -> str:
    h = hashlib.sha256()
    for part in (provider, model, f"{temperature:.3f}", str(max_tokens),
                 system or "", prompt, spec_sig):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


class _Cache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[LLMResponse]:
        p = self.root / f"{key}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        d.pop("cached", None)
        d.pop("total_tokens", None)
        resp = LLMResponse(**d)
        resp.cached = True
        return resp

    def put(self, key: str, resp: LLMResponse) -> None:
        d = asdict(resp)
        d["total_tokens"] = resp.total_tokens
        (self.root / f"{key}.json").write_text(json.dumps(d, indent=2))


# --------------------------------------------------------------------------- #
# Provider base + backends
# --------------------------------------------------------------------------- #

class LLMProvider:
    """Base class implementing the cache; subclasses implement `_raw_complete`."""

    name = "base"

    def __init__(self, model: str, cache_dir: Path = DEFAULT_CACHE):
        self.model = model
        self.cache = _Cache(cache_dir)

    def _raw_complete(self, prompt: str, system: Optional[str],
                      temperature: float, max_tokens: int,
                      mock_spec: Optional[dict]) -> LLMResponse:
        raise NotImplementedError

    def complete(self, prompt: str, *, system: Optional[str] = None,
                 temperature: float = 0.0, max_tokens: int = 2048,
                 mock_spec: Optional[dict] = None,
                 use_cache: bool = True) -> LLMResponse:
        spec_sig = ""
        if mock_spec is not None:
            spec_sig = hashlib.sha256(
                json.dumps(mock_spec, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
        key = _cache_key(self.name, self.model, temperature, max_tokens,
                         system, prompt, spec_sig)
        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        resp = self._raw_complete(prompt, system, temperature, max_tokens, mock_spec)
        if use_cache:
            self.cache.put(key, resp)
        return resp


class MockProvider(LLMProvider):
    """Deterministic, prompt-driven simulator. See module docstring."""

    name = "mock"

    def __init__(self, model: str = "mock-deterministic-v1",
                 cache_dir: Path = DEFAULT_CACHE):
        super().__init__(model, cache_dir)

    def _raw_complete(self, prompt, system, temperature, max_tokens, mock_spec):
        if mock_spec is None:
            text = self._echo(prompt)
        elif mock_spec.get("task") == "generate_rdf":
            text = self._generate_rdf(mock_spec)
        elif mock_spec.get("task") == "answer":
            text = self._answer(mock_spec)
        else:
            text = self._echo(prompt)
        return LLMResponse(
            text=text, provider=self.name, model=self.model,
            prompt_tokens=estimate_tokens((system or "") + prompt),
            completion_tokens=estimate_tokens(text),
        )

    # -- mock behaviours ---------------------------------------------------- #

    @staticmethod
    def _echo(prompt: str) -> str:
        return f"[mock] {prompt.strip()[:200]}"

    @staticmethod
    def _generate_rdf(spec: dict) -> str:
        """Emit Turtle for a ClinicalQuestionHolon + its EvidenceAssertion(s).

        Two emission classes, mirroring how a real model behaves:

        * **Assertion fields** (confidence, level, provenance, citation) are
          *natural* content read straight off the admissible evidence block, so the
          mock always emits them — both systems produce a valid reifier.
        * **Holon-layer scaffold** (the four layer graphs, question/answer text,
          quality threshold) is *shape-specific* structure a naive model does not
          know to emit. The mock emits it only when `emit_holon_scaffold` is set
          (the SHACL-guided System A) or when a field has been named back to it
          via `repair_fields` (the validate->repair loop). System B therefore
          fails the first pass on the holon shape and converges as the SHACL
          report feeds the missing paths back.

        Naive retrieval also surfaces `noise_facts`, which the mock turns into
        ungrounded `oe:treats` triples — the hallucination signal evaluated in
        §3.3 Deney 2.
        """
        required = set(spec.get("required_fields", []))
        repaired = set(spec.get("repair_fields", []))
        emit_scaffold = spec.get("emit_holon_scaffold", False)
        facts = spec.get("facts", [])
        noise = spec.get("noise_facts", [])
        holon = spec.get("holon_uri", f"{_OEQ}q_generated")
        hid = spec.get("holon_id", "g")

        def want(field: str) -> bool:
            return emit_scaffold or field in required or field in repaired

        lines = [
            f"@prefix holon: <{_HOLON}> .",
            f"@prefix oe: <{_OE}> .",
            f"@prefix oeq: <{_OEQ}> .",
            f"@prefix oegen: <{_OEGEN}> .",
            f"@prefix rdf: <{_RDF}> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            f"@prefix xsd: <{_XSD}> .",
            "",
        ]
        # Holon node — always typed (so the shape has a target), structural
        # properties gated by want().
        holon_props = []
        if want("oe:questionText"):
            holon_props.append(f'oe:questionText "{_esc(spec.get("question", "?"))}"^^xsd:string')
        if want("oe:answerText"):
            holon_props.append(f'oe:answerText "{_esc(spec.get("answer_text", "Generated answer."))}"^^xsd:string')
        if want("oe:belongsToSpecialty"):
            holon_props.append(f'oe:belongsToSpecialty "{spec.get("specialty", "General Medicine")}"')
        for layer in ("Interior", "Boundary", "Projection", "Context"):
            if want(f"holon:has{layer}Graph"):
                holon_props.append(f"holon:has{layer}Graph <{holon}-{layer[:3].lower()}>")
        if want("holon:evidenceQualityThreshold"):
            # Calibrate the threshold to the holon's own evidence so a faithfully
            # generated holon is internally consistent (never self-triggers T4a:
            # 'effective below threshold'). thr = min(0.5, min fact confidence).
            confs = [float(f.get("confidence", 0.8)) for f in facts] or [0.5]
            thr = min(0.5, min(confs))
            holon_props.append(f'holon:evidenceQualityThreshold "{thr:.2f}"^^xsd:decimal')

        if holon_props:
            lines.append(f"<{holon}> a holon:ClinicalQuestionHolon ;")
            for i, p in enumerate(holon_props):
                lines.append(f"    {p}{' ;' if i < len(holon_props) - 1 else ' .'}")
        else:
            lines.append(f"<{holon}> a holon:ClinicalQuestionHolon .")
        lines.append("")

        # Evidence assertions — always fully emitted (natural content).
        for k, fct in enumerate(facts):
            ev = f"{_OEGEN}ev_{hid}_{k}"
            tt = f"{ev}-tt"
            lines += [
                f"<{fct['s']}> oe:treats <{fct['o']}> .",
                f"<{ev}> a holon:EvidenceAssertion ;",
                f"    rdf:reifies <{tt}> ;",
                f'    holon:confidence "{float(fct.get("confidence", 0.8)):.2f}"^^xsd:decimal ;',
                f'    holon:evidenceLevel "{fct.get("level", "Level-1A")}" ;',
                f"    holon:assessedBy <{_OEQ}openevidence_ai> ;",
                f'    holon:recordedOn "{fct.get("recorded", "2026-12-31")}"^^xsd:date ;',
                f"    oe:cites <{fct['source']}> ;",
                f"    holon:inHolon <{holon}> ;",
                f'    oe:effectiveness "{fct.get("effectiveness", "effective")}" .',
                f"<{tt}> rdf:subject <{fct['s']}> ;",
                "    rdf:predicate oe:treats ;",
                f"    rdf:object <{fct['o']}> .",
                "",
            ]
        # Naive over-generation from noisy context -> ungrounded triples.
        for nf in noise:
            lines.append(f"<{nf['s']}> oe:treats <{nf['o']}> .   # ungrounded (naive)")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _answer(spec: dict) -> str:
        """Natural-language answer: grounded facts (+ naive noise)."""
        facts = spec.get("facts", [])
        noise = spec.get("noise_facts", [])
        parts = []
        for f in facts:
            parts.append(
                f"{_local(f['s'])} is indicated for {_local(f['o'])} "
                f"(confidence {f.get('confidence', 0.8):.2f}, {f.get('level', 'Level-1A')})."
            )
        for nf in noise:
            parts.append(f"{_local(nf['s'])} also treats {_local(nf['o'])}.")
        if not parts:
            parts.append("No grounded evidence was retrieved for this question.")
        return " ".join(parts)


def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _local(uri: str) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1].replace("_", " ")


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: Optional[str] = None, cache_dir: Path = DEFAULT_CACHE):
        super().__init__(model or "gpt-5.4-mini-2026-03-17", cache_dir)

    def _raw_complete(self, prompt, system, temperature, max_tokens, mock_spec):
        try:
            from openai import OpenAI            # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed; `pip install openai` or use the "
                "default mock provider (unset P3_LLM_PROVIDER)."
            ) from e
        client = OpenAI()
        out = client.responses.create(
            model=self.model,
            instructions=system or None,
            input=prompt,
            max_output_tokens=max_tokens,
        )
        usage = out.usage
        return LLMResponse(
            text=out.output_text or "",
            provider=self.name, model=self.model,
            prompt_tokens=getattr(usage, "input_tokens", 0),
            completion_tokens=getattr(usage, "output_tokens", 0),
        )


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: Optional[str] = None, cache_dir: Path = DEFAULT_CACHE):
        super().__init__(model or "claude-sonnet-5", cache_dir)

    def _raw_complete(self, prompt, system, temperature, max_tokens, mock_spec):
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "anthropic package not installed; `pip install anthropic` or use "
                "the default mock provider (unset P3_LLM_PROVIDER)."
            ) from e
        client = anthropic.Anthropic()
        out = client.messages.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature,
            system=system or "", messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in out.content if getattr(b, "type", "") == "text")
        return LLMResponse(
            text=text, provider=self.name, model=self.model,
            prompt_tokens=out.usage.input_tokens,
            completion_tokens=out.usage.output_tokens,
        )


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: Optional[str] = None, cache_dir: Path = DEFAULT_CACHE):
        super().__init__(model or "qwen3:8b", cache_dir)

    def _raw_complete(self, prompt, system, temperature, max_tokens, mock_spec):
        try:
            import ollama
        except ImportError as e:
            raise RuntimeError(
                "ollama package not installed; `pip install ollama` and run the "
                "Ollama daemon, or use the default mock provider."
            ) from e
        out = ollama.chat(
            model=self.model,
            messages=([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": prompt}],
            think=False,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        text = out["message"]["content"]
        return LLMResponse(
            text=text, provider=self.name, model=self.model,
            prompt_tokens=out.get("prompt_eval_count", estimate_tokens(prompt)),
            completion_tokens=out.get("eval_count", estimate_tokens(text)),
        )


_PROVIDERS = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: Optional[str] = None, model: Optional[str] = None,
                 cache_dir: Path = DEFAULT_CACHE) -> LLMProvider:
    """Factory. Resolves the provider from the argument, then env, then mock."""
    name = (name or os.environ.get("P3_LLM_PROVIDER", "mock")).lower()
    model = model or os.environ.get("P3_LLM_MODEL")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Choose from {list(_PROVIDERS)}.")
    return cls(model=model, cache_dir=cache_dir) if model else cls(cache_dir=cache_dir)


if __name__ == "__main__":
    p = get_provider()
    demo_spec = {
        "task": "generate_rdf", "holon_id": "demo", "question": "Demo?",
        "required_fields": ["holon:confidence", "holon:evidenceLevel",
                            "holon:assessedBy", "holon:recordedOn", "oe:cites",
                            "holon:inHolon"],
        "facts": [{"s": "https://example.org/openevidence/drugs/lisinopril",
                   "o": "https://example.org/openevidence/diseases/hypertension",
                   "source": "https://example.org/openevidence/sources/34567890",
                   "confidence": 0.95, "level": "Level-1A"}],
    }
    r = p.complete("demo prompt", mock_spec=demo_spec)
    print(f"provider={r.provider} model={r.model} cached={r.cached} "
          f"tokens={r.total_tokens}\n{r.text}")
