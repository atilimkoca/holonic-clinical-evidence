"""graph_rag.py — Dual RAG architecture (§3.2): holon-based vs naive GraphRAG.

Two retrieval/prompting strategies over Project 1's holonic corpus, sharing the
same LLM, question set and metrics so only the *design* varies:

System A — Holon-Based GraphRAG (proposed)
    * retrieves the boundary-relevant holon (context window = holon boundary);
    * uses only the PROJECTION layer + confidence-filtered grounded facts;
    * prepends the SHACL shape as a prompt prefix (SHACL-guided);
    * confidence-weighted -> no cross-holon noise -> low hallucination, small ctx.

System B — Naive GraphRAG (baseline)
    * vector-similarity retrieval over ALL triples (top-k holons unioned);
    * dumps raw triples, no holon boundary, no SHACL, no confidence filter;
    * over-fetches loosely related facts -> ungrounded "noise" -> hallucination.

Ablation systems (reviewer request): A and B differ in TWO factors at once
(boundary-scoped retrieval and SHACL-guided prompting). Systems C and D vary
exactly one factor each so the effect can be attributed:

System C — boundary-scoped retrieval + naive prompt (no SHACL guidance)
System D — naive top-k retrieval + SHACL-guided prompt

The retrieval side of the ablation lives here (SYSTEM_RETRIEVAL); the prompt
side lives in llm_generator.SHACL_GUIDED_SYSTEMS.

The retriever is a deterministic TF-IDF cosine index (no heavy deps; a neural
encoder is optional, see README Threats to Validity).
"""
from __future__ import annotations

import math
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dataset import Question, load_testset                         # noqa: E402
from llm_provider import estimate_tokens                              # noqa: E402

QUALITY_THRESHOLD = 0.50          # holon evidenceQualityThreshold (matches Set A)
TOP_K = 5                         # naive retrieval breadth
MAX_NOISE = 4                     # cap on naive over-generation per question

# Which retrieval strategy each system uses (the prompt factor is decided in
# llm_generator). A/C share the boundary-scoped retriever, B/D the naive one.
SYSTEM_RETRIEVAL = {"A": "boundary", "B": "naive", "C": "boundary", "D": "naive"}
_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list:
    return _WORD.findall(text.lower())


# --------------------------------------------------------------------------- #
# Deterministic TF-IDF retriever
# --------------------------------------------------------------------------- #

class TfidfRetriever:
    """Tiny, deterministic TF-IDF cosine retriever over holon documents."""

    def __init__(self, docs: dict):
        # docs: id -> text
        self.ids = sorted(docs)
        self.tokens = {i: _tokenize(docs[i]) for i in self.ids}
        df: Counter = Counter()
        for i in self.ids:
            df.update(set(self.tokens[i]))
        n = len(self.ids)
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self.vecs = {i: self._vec(self.tokens[i]) for i in self.ids}

    def _vec(self, toks: list) -> dict:
        tf = Counter(toks)
        v = {t: (c / len(toks)) * self.idf.get(t, 0.0) for t, c in tf.items()} if toks else {}
        norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
        return {t: w / norm for t, w in v.items()}

    def retrieve(self, query: str, top_k: int = TOP_K) -> list:
        qv = self._vec(_tokenize(query))
        scored = []
        for i in self.ids:
            dv = self.vecs[i]
            # cosine = dot (both normalised); iterate the smaller vector
            small, big = (qv, dv) if len(qv) < len(dv) else (dv, qv)
            dot = sum(w * big.get(t, 0.0) for t, w in small.items())
            scored.append((i, dot))
        scored.sort(key=lambda kv: (-kv[1], kv[0]))
        return scored[:top_k]


@dataclass
class RetrievalContext:
    holon_id: str
    system: str
    question: str
    holon_uri: str
    specialty: str
    gold_answer: str
    facts: list = field(default_factory=list)          # grounded (drug-disease)
    noise_facts: list = field(default_factory=list)     # ungrounded (naive only)
    retrieved_ids: list = field(default_factory=list)
    context_tokens: int = 0
    retrieval_seconds: float = 0.0

    def to_generator_context(self) -> dict:
        f0 = self.facts[0] if self.facts else {}
        return {
            "holon_id": self.holon_id, "holon_uri": self.holon_uri,
            "question": self.question, "answer_text": self.gold_answer,
            "specialty": self.specialty, "facts": self.facts,
            "noise_facts": self.noise_facts,
        }


class DualRAG:
    def __init__(self, questions: Optional[list] = None):
        self.questions = questions or load_testset()
        self.by_id = {q.holon_id: q for q in self.questions}
        docs = {q.holon_id: f"{q.question} {q.gold_answer} {q.specialty}"
                for q in self.questions}
        self.retriever = TfidfRetriever(docs)

    # -- System A/C: holon-based, projection-only, confidence-WEIGHTED ------- #
    def context_A(self, q: Question, system: str = "A") -> RetrievalContext:
        t0 = time.perf_counter()
        ranked = self.retriever.retrieve(q.question, top_k=1)
        dt = time.perf_counter() - t0
        # Bounded to the single best holon (its own). Confidence-weighting orders
        # facts by confidence but does NOT drop the holon's own grounded answer
        # (so coverage is preserved); the holon boundary is what excludes the
        # cross-holon noise that System B admits.
        facts = sorted(q.facts, key=lambda f: -float(f["confidence"]))
        # projection-only context string (summary + facts) + SHACL prefix
        ctx_str = (q.question + " " + q.gold_answer
                   + " ".join(_fact_str(f) for f in facts)
                   + " SHACL:ClinicalQuestionShape+EvidenceReifierShape")
        return RetrievalContext(
            holon_id=q.holon_id, system=system, question=q.question,
            holon_uri=q.holon_uri, specialty=q.specialty, gold_answer=q.gold_answer,
            facts=facts, noise_facts=[], retrieved_ids=[i for i, _ in ranked],
            context_tokens=estimate_tokens(ctx_str), retrieval_seconds=dt,
        )

    # -- System B/D: naive, top-k union of raw triples, unfiltered ----------- #
    def context_B(self, q: Question, system: str = "B") -> RetrievalContext:
        t0 = time.perf_counter()
        ranked = self.retriever.retrieve(q.question, top_k=TOP_K)
        dt = time.perf_counter() - t0
        facts = list(q.facts)                                  # unfiltered grounded
        grounded_keys = {(f["s"], f["o"]) for f in facts}
        # Over-fetch: naive retrieval dumps the facts of EVERY top-k holon it
        # ranked, not just the answer holon. The neighbours' facts (different
        # drug-disease pairs) are real corpus facts but ungrounded for THIS
        # question -> the hallucination surface the holon boundary excludes.
        noise = []
        for hid, _ in ranked[1:]:                  # skip the top-1 (answer holon)
            nq = self.by_id.get(hid)
            if not nq:
                continue
            for f in nq.facts:
                if (f["s"], f["o"]) not in grounded_keys:
                    noise.append(dict(f))
        # de-dup + cap, deterministic order
        seen, uniq = set(), []
        for nf in sorted(noise, key=lambda x: (x["s"], x["source"])):
            k = (nf["s"], nf["o"])
            if k in seen or k in grounded_keys:
                continue
            seen.add(k)
            uniq.append(nf)
        uniq = uniq[:MAX_NOISE]
        # raw-triple dump context string (all triples from top-k holons)
        raw = []
        for hid, _ in ranked:
            qq = self.by_id.get(hid)
            if qq:
                raw.append(qq.question + " " + qq.gold_answer)
                raw += [_fact_str(f) for f in qq.facts]
        ctx_str = " ".join(raw)
        return RetrievalContext(
            holon_id=q.holon_id, system=system, question=q.question,
            holon_uri=q.holon_uri, specialty=q.specialty, gold_answer=q.gold_answer,
            facts=facts, noise_facts=uniq, retrieved_ids=[i for i, _ in ranked],
            context_tokens=estimate_tokens(ctx_str), retrieval_seconds=dt,
        )

    def context(self, q: Question, system: str) -> RetrievalContext:
        strategy = SYSTEM_RETRIEVAL.get(system)
        if strategy == "boundary":
            return self.context_A(q, system=system)
        if strategy == "naive":
            return self.context_B(q, system=system)
        raise ValueError(f"Unknown system '{system}'; expected one of "
                         f"{sorted(SYSTEM_RETRIEVAL)}.")


def _fact_str(f: dict) -> str:
    return (f"{_local(f['s'])} treats {_local(f['o'])} "
            f"conf {f['confidence']} {f['level']} src {_local(f['source'])} "
            f"{f.get('effectiveness') or ''}")


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    rag = DualRAG()
    q = rag.questions[0]
    a = rag.context(q, "A")
    b = rag.context(q, "B")
    print(f"Question: {q.question[:70]}")
    print(f"System A: facts={len(a.facts)} noise={len(a.noise_facts)} "
          f"ctx_tokens={a.context_tokens} retrieved={a.retrieved_ids}")
    print(f"System B: facts={len(b.facts)} noise={len(b.noise_facts)} "
          f"ctx_tokens={b.context_tokens} retrieved={b.retrieved_ids[:3]}...")
    # corpus-wide averages
    import statistics as st
    at = [rag.context(qq, "A").context_tokens for qq in rag.questions]
    bt = [rag.context(qq, "B").context_tokens for qq in rag.questions]
    bn = [len(rag.context(qq, "B").noise_facts) for qq in rag.questions]
    print(f"Avg ctx tokens: A={st.mean(at):.0f}  B={st.mean(bt):.0f}")
    print(f"Avg naive noise facts/question (B): {st.mean(bn):.2f}")


if __name__ == "__main__":
    main()
