"""graph_analysis.py — holon-level graph topology, community detection,
cross-level centrality, and holon homomorphism / subsumption (assignment §1.4).

The holon-level graph treats each clinical-question holon as a node and links two
holons when they share a medical entity (the same disease or the same drug). We
then ask the assignment's questions:

  * What is the degree distribution / clustering / betweenness structure?
  * Does community detection recover medical specialties? (modularity, purity,
    NMI, adjusted Rand index against the specialty ground truth)
  * Cross-level: are *structurally* central holons also *semantically* central?
    (Spearman correlation of betweenness vs evidence strength)
  * Holon homomorphism & subsumption: >=4 holon-level patterns and 2 worked
    subsumption pairs H1 ⊑ H2 with an explicit projection homomorphism.

Outputs:
  results/graph_metrics.json
  results/graph_analysis.md
  results/figures/degree_distribution.png
  results/figures/community_vs_specialty.png
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from scipy.stats import spearmanr

from . import config as C


# --- clustering-comparison metrics (no sklearn dependency) -------------------
def _contingency(labels_a: list, labels_b: list) -> dict:
    tab: dict = defaultdict(lambda: defaultdict(int))
    for x, y in zip(labels_a, labels_b):
        tab[x][y] += 1
    return tab


def normalized_mutual_information(true: list, pred: list) -> float:
    n = len(true)
    tab = _contingency(true, pred)
    a = Counter(true); b = Counter(pred)
    mi = 0.0
    for x, row in tab.items():
        for y, nxy in row.items():
            if nxy == 0:
                continue
            mi += (nxy / n) * math.log((nxy * n) / (a[x] * b[y]))
    hx = -sum((c / n) * math.log(c / n) for c in a.values())
    hy = -sum((c / n) * math.log(c / n) for c in b.values())
    return mi / math.sqrt(hx * hy) if hx > 0 and hy > 0 else 0.0


def adjusted_rand_index(true: list, pred: list) -> float:
    tab = _contingency(true, pred)
    n = len(true)
    comb2 = lambda k: k * (k - 1) // 2
    sum_ij = sum(comb2(nxy) for row in tab.values() for nxy in row.values())
    a = Counter(true); b = Counter(pred)
    sum_a = sum(comb2(c) for c in a.values())
    sum_b = sum(comb2(c) for c in b.values())
    expected = sum_a * sum_b / comb2(n) if comb2(n) else 0
    max_index = 0.5 * (sum_a + sum_b)
    return (sum_ij - expected) / (max_index - expected) if (max_index - expected) else 0.0


def purity(true: list, pred: list) -> float:
    tab = _contingency(pred, true)              # cluster -> {specialty: count}
    return sum(max(row.values()) for row in tab.values()) / len(true)


# --- graph construction ------------------------------------------------------
def build_holon_graph(holons: list, entities: dict) -> nx.Graph:
    """Nodes = clinical-question holons; edges link holons that share a medical
    entity: the same disease, the same drug, or the same drug *class* (a
    pharmacology bridge). Disease/drug links create tight within-topic cliques;
    drug-class links bridge related diseases, giving the graph non-trivial
    betweenness structure without the promiscuous over-connection that generic
    shared symptoms (e.g. 'fatigue') would introduce across unrelated specialties."""
    G = nx.Graph()
    for h in holons:
        G.add_node(h["id"], specialty=h["specialty"], disease=h["disease"],
                   drug=h["drug"] or "none", facet=h["facet"],
                   confidence=h["confidence"],
                   aggregate=h["aggregate_confidence"],
                   n_citations=len(h["citations"]))
    index: dict[tuple, list] = defaultdict(list)
    for h in holons:
        index[("disease", h["disease"])].append(h["id"])
        if h["drug"]:
            index[("drug", h["drug"])].append(h["id"])
        if h["drug_class"]:
            index[("class", h["drug_class"])].append(h["id"])
    for (kind, _key), members in index.items():
        for u, v in combinations(set(members), 2):
            if G.has_edge(u, v):
                G[u][v]["weight"] += 1
                G[u][v]["via"].add(kind)
            else:
                G.add_edge(u, v, weight=1, via={kind})
    return G


# --- holon homomorphism / subsumption ----------------------------------------
def holon_signature(h: dict) -> set[str]:
    """Projection/interior signature of a holon as a set of structural features."""
    sig = {f"facet:{h['facet']}", f"specialty:{h['specialty']}",
           f"evidence:{h['evidence_level']}"}
    if h["relation"]:
        sig.add(f"relation:{h['relation']}")
    if h["drug_class"]:
        sig.add(f"class:{h['drug_class']}")
    if h["confidence"] >= 0.9:
        sig.add("high-confidence")
    if h["effectiveness"] == "effective":
        sig.add("effective")
    return sig


PATTERNS = {
    "P1_high_conf_treatment": {"facet:treatment", "relation:treats", "high-confidence"},
    "P2_effective_with_1A":   {"relation:treats", "evidence:Level-1A", "effective"},
    "P3_side_effect":         {"facet:safety", "relation:causesSideEffect"},
    "P4_cardiology_treatment":{"specialty:Cardiology", "relation:treats"},
}


def match_patterns(holons: list) -> dict[str, list[str]]:
    """A holon matches a pattern iff the pattern's features homomorphically map
    into the holon's signature (i.e., pattern ⊆ signature)."""
    out: dict[str, list[str]] = {p: [] for p in PATTERNS}
    sigs = {h["id"]: holon_signature(h) for h in holons}
    for p, feats in PATTERNS.items():
        for hid, sig in sigs.items():
            if feats <= sig:
                out[p].append(hid)
    return out


def find_subsumptions(holons: list, limit: int = 2) -> list[dict]:
    """H1 ⊑ H2 iff sig(H2) ⊆ sig(H1): the more specific holon (H1) contains a
    homomorphic image of the more general holon (H2)'s projection signature."""
    sigs = {h["id"]: holon_signature(h) for h in holons}
    pairs: list[dict] = []
    ids = list(sigs)
    for a, b in combinations(ids, 2):
        sa, sb = sigs[a], sigs[b]
        if sa == sb:
            continue
        if sb < sa:           # b more general, a more specific  => a ⊑ b
            specific, general = a, b
        elif sa < sb:
            specific, general = b, a
        else:
            continue
        pairs.append({
            "specific": specific, "general": general,
            "phi": sorted(sigs[general]),
            "extra_in_specific": sorted(sigs[specific] - sigs[general]),
        })
        if len(pairs) >= limit:
            break
    return pairs


# --- main --------------------------------------------------------------------
def analyse() -> dict[str, Any]:
    C.ensure_dirs()
    holons = json.loads((C.PROCESSED_DIR / "holons.json").read_text("utf-8"))
    entities = json.loads((C.PROCESSED_DIR / "entities.json").read_text("utf-8"))
    G = build_holon_graph(holons, entities)

    degrees = [d for _, d in G.degree()]
    betw = nx.betweenness_centrality(G, weight="weight")
    clustering = nx.average_clustering(G)
    components = list(nx.connected_components(G))
    largest = max(components, key=len)

    # community detection
    communities = list(nx.community.greedy_modularity_communities(G, weight="weight"))
    node_comm = {}
    for i, com in enumerate(communities):
        for n in com:
            node_comm[n] = i
    nodes = list(G.nodes())
    true_spec = [G.nodes[n]["specialty"] for n in nodes]
    pred_comm = [node_comm[n] for n in nodes]
    modularity = nx.community.modularity(G, communities, weight="weight")

    # cross-level: structural (betweenness) vs semantic (aggregate confidence)
    bt = [betw[n] for n in nodes]
    sem = [G.nodes[n]["aggregate"] for n in nodes]
    rho, pval = spearmanr(bt, sem)
    # divergent holons: top structural but low semantic, and vice versa
    bt_rank = {n: r for r, n in enumerate(sorted(nodes, key=lambda x: betw[x], reverse=True))}
    sem_rank = {n: r for r, n in enumerate(sorted(nodes, key=lambda x: G.nodes[x]["aggregate"], reverse=True))}
    divergent = sorted(nodes, key=lambda n: abs(bt_rank[n] - sem_rank[n]), reverse=True)[:5]

    patterns = match_patterns(holons)
    subsumptions = find_subsumptions(holons, limit=2)

    metrics = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "density": round(nx.density(G), 4),
        "avg_degree": round(sum(degrees) / len(degrees), 2),
        "max_degree": max(degrees),
        "avg_clustering_coefficient": round(clustering, 4),
        "n_connected_components": len(components),
        "largest_component_size": len(largest),
        "community_detection": {
            "n_communities": len(communities),
            "modularity": round(modularity, 4),
            "purity_vs_specialty": round(purity(true_spec, pred_comm), 4),
            "NMI_vs_specialty": round(normalized_mutual_information(true_spec, pred_comm), 4),
            "ARI_vs_specialty": round(adjusted_rand_index(true_spec, pred_comm), 4),
            "n_specialties": len(set(true_spec)),
        },
        "cross_level": {
            "spearman_betweenness_vs_aggregate_confidence": round(float(rho), 4),
            "p_value": round(float(pval), 4),
            "most_divergent_holons": divergent,
        },
        "top_betweenness": sorted(
            ({"holon": n, "betweenness": round(betw[n], 4),
              "specialty": G.nodes[n]["specialty"]} for n in nodes),
            key=lambda x: x["betweenness"], reverse=True)[:8],
        "homomorphism_patterns": {p: len(v) for p, v in patterns.items()},
        "homomorphism_pattern_examples": {p: v[:3] for p, v in patterns.items()},
        "subsumption_pairs": subsumptions,
    }

    _figures(degrees, nodes, true_spec, pred_comm, G, betw)
    (C.RESULTS_DIR / "graph_metrics.json").write_text(json.dumps(metrics, indent=2), "utf-8")
    _write_md(metrics)

    print("Graph-topology analysis complete:")
    print(f"  nodes={metrics['n_nodes']} edges={metrics['n_edges']} "
          f"avg_deg={metrics['avg_degree']} clustering={metrics['avg_clustering_coefficient']}")
    cd = metrics["community_detection"]
    print(f"  communities={cd['n_communities']} modularity={cd['modularity']} "
          f"purity={cd['purity_vs_specialty']} NMI={cd['NMI_vs_specialty']} ARI={cd['ARI_vs_specialty']}")
    print(f"  cross-level Spearman(betweenness,confidence)={metrics['cross_level']['spearman_betweenness_vs_aggregate_confidence']} "
          f"(p={metrics['cross_level']['p_value']})")
    print(f"  homomorphism pattern matches: {metrics['homomorphism_patterns']}")
    print(f"  subsumption pairs found: {len(subsumptions)}")
    return metrics


def _figures(degrees, nodes, true_spec, pred_comm, G, betw) -> None:
    # degree distribution
    plt.figure(figsize=(6, 4))
    plt.hist(degrees, bins=range(min(degrees), max(degrees) + 2), color="#3b6ea5", edgecolor="white")
    plt.xlabel("degree"); plt.ylabel("number of holons")
    plt.title("Holon-level degree distribution")
    plt.tight_layout(); plt.savefig(C.FIGURES_DIR / "degree_distribution.png", dpi=130); plt.close()

    # community vs specialty (stacked composition)
    comm_spec: dict = defaultdict(Counter)
    for n, c in zip(nodes, pred_comm):
        comm_spec[c][G.nodes[n]["specialty"]] += 1
    specialties = sorted({s for s in true_spec})
    comms = sorted(comm_spec)
    bottom = [0] * len(comms)
    plt.figure(figsize=(8, 4.5))
    cmap = plt.get_cmap("tab10")
    for i, sp in enumerate(specialties):
        vals = [comm_spec[c].get(sp, 0) for c in comms]
        plt.bar([str(c) for c in comms], vals, bottom=bottom, label=sp, color=cmap(i % 10))
        bottom = [b + v for b, v in zip(bottom, vals)]
    plt.xlabel("detected community"); plt.ylabel("# holons")
    plt.title("Detected communities vs. medical specialty")
    plt.legend(fontsize=7, ncol=2, loc="upper right")
    plt.tight_layout(); plt.savefig(C.FIGURES_DIR / "community_vs_specialty.png", dpi=130); plt.close()


def _write_md(m: dict) -> None:
    cd = m["community_detection"]; cl = m["cross_level"]
    lines = [
        "# Holon-Level Graph Topology Analysis", "",
        "## Global structure", "",
        f"- Nodes (clinical-question holons): **{m['n_nodes']}**",
        f"- Edges (shared disease/drug): **{m['n_edges']}**, density {m['density']}",
        f"- Average degree {m['avg_degree']}, max degree {m['max_degree']}",
        f"- Average clustering coefficient: **{m['avg_clustering_coefficient']}**",
        f"- Connected components: {m['n_connected_components']} "
        f"(largest {m['largest_component_size']})", "",
        "## Community detection vs. medical specialty", "",
        f"- Communities detected (greedy modularity): **{cd['n_communities']}** "
        f"(vs {cd['n_specialties']} specialties)",
        f"- Modularity: **{cd['modularity']}**",
        f"- Purity: **{cd['purity_vs_specialty']}**, "
        f"NMI: **{cd['NMI_vs_specialty']}**, ARI: **{cd['ARI_vs_specialty']}**",
        "",
        "Interpretation: high purity/NMI means holon clusters (built only from "
        "shared diseases/drugs) substantially recover the medical-specialty "
        "partition — i.e., topology encodes domain structure.", "",
        "## Cross-level centrality (structural vs. semantic)", "",
        f"- Spearman(betweenness, aggregate confidence) = "
        f"**{cl['spearman_betweenness_vs_aggregate_confidence']}** (p={cl['p_value']})",
        f"- Most divergent holons (structurally central but semantically peripheral, "
        f"or vice versa): `{', '.join(cl['most_divergent_holons'])}`",
        "",
        "This extends the midterm 'structurally vs semantically central' question: "
        "a weak/insignificant correlation means a holon's bridging role in the "
        "graph is largely independent of its evidence strength.", "",
        "## Holon homomorphism — pattern matches", "",
        "| Pattern | features | #holons |",
        "|---------|----------|---------|",
    ]
    for p, feats in PATTERNS.items():
        lines.append(f"| `{p}` | {', '.join(sorted(feats))} | {m['homomorphism_patterns'][p]} |")
    lines += ["", "## Subsumption pairs (H_specific ⊑ H_general)", ""]
    for i, s in enumerate(m["subsumption_pairs"], 1):
        lines += [
            f"**Pair {i}:** `{s['specific']}` ⊑ `{s['general']}`",
            f"- homomorphism φ maps the general projection signature "
            f"{{{', '.join(s['phi'])}}} into the specific holon;",
            f"- extra (specialising) features in the specific holon: "
            f"{{{', '.join(s['extra_in_specific'])}}}", "",
        ]
    (C.RESULTS_DIR / "graph_analysis.md").write_text("\n".join(lines), "utf-8")


def main() -> None:
    argparse.ArgumentParser(description="Holon-level graph topology analysis.").parse_args()
    analyse()


if __name__ == "__main__":
    main()
