"""
Tonnetz graph models.

G1  pitch-class Tonnetz : 12 nodes (pitch classes), 36 edges (fifth / major third / minor third)
G2  chord graph (dual)  : 24 nodes (major and minor triads), 36 edges (P / L / R operations)

Run this file directly to print the structural checks:
    python tonnetz.py
"""
from itertools import combinations

import networkx as nx

NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# interval in semitones -> edge label
INTERVALS = {7: "P5", 4: "M3", 3: "m3"}


# ---------------------------------------------------------------- G1
def build_pitch_tonnetz():
    """12 pitch classes; an edge joins notes a fifth, major third or minor third apart."""
    g = nx.Graph(name="G1 pitch-class Tonnetz")
    for pc in range(12):
        g.add_node(pc, name=NOTE_NAMES[pc])
    for pc in range(12):
        for semitones, label in INTERVALS.items():
            g.add_edge(pc, (pc + semitones) % 12, interval=label)
    return g


# ---------------------------------------------------------------- G2
def triad_notes(root, quality):
    """Pitch classes of a major ('maj') or minor ('min') triad."""
    third = 4 if quality == "maj" else 3
    return frozenset({root % 12, (root + third) % 12, (root + 7) % 12})


def triad_name(root, quality):
    return NOTE_NAMES[root % 12] + ("" if quality == "maj" else "m")


def plr(root, quality):
    """The three neo-Riemannian neighbours of a triad, as {operation: (root, quality)}."""
    if quality == "maj":
        return {
            "P": (root, "min"),               # C  -> Cm
            "R": ((root + 9) % 12, "min"),    # C  -> Am
            "L": ((root + 4) % 12, "min"),    # C  -> Em
        }
    return {
        "P": (root, "maj"),                   # Cm -> C
        "R": ((root + 3) % 12, "maj"),        # Cm -> Eb
        "L": ((root + 8) % 12, "maj"),        # Cm -> Ab
    }


def build_chord_graph():
    """24 triads; an edge joins two triads that share two notes (labelled P, L or R)."""
    g = nx.Graph(name="G2 chord graph")
    for root in range(12):
        for quality in ("maj", "min"):
            g.add_node((root, quality), name=triad_name(root, quality),
                       notes=sorted(triad_notes(root, quality)))
    for node in list(g.nodes):
        for op, other in plr(*node).items():
            g.add_edge(node, other, op=op)
    return g


# ---------------------------------------------------------------- helpers
def op_path(g2, source, target):
    """Shortest path between two triads as a string of P/L/R letters."""
    path = nx.shortest_path(g2, source, target)
    return "".join(g2.edges[a, b]["op"] for a, b in zip(path, path[1:]))


def cycles_from_ops(g2, op_a, op_b):
    """Cycles obtained by alternating two operations (e.g. P and L -> hexatonic cycles)."""
    seen, cycles = set(), []
    for start in g2.nodes:
        if start in seen:
            continue
        cycle, node, ops = [start], start, (op_a, op_b)
        i = 0
        while True:
            node = plr(*node)[ops[i % 2]]
            i += 1
            if node == start and i % 2 == 0:
                break
            cycle.append(node)
        seen.update(cycle)
        cycles.append(cycle)
    return cycles


def count_hamiltonian_cycles(g):
    """Count Hamiltonian cycles by backtracking (fine for a 24-node cubic graph)."""
    nodes = list(g.nodes)
    start, n = nodes[0], len(nodes)
    count = 0
    visited = {start}

    def extend(node, depth):
        nonlocal count
        if depth == n:
            if g.has_edge(node, start):
                count += 1
            return
        for nxt in g.neighbors(node):
            if nxt not in visited:
                visited.add(nxt)
                extend(nxt, depth + 1)
                visited.remove(nxt)

    extend(start, 1)
    return count // 2          # each cycle is found once in each direction


def structural_report():
    g1, g2 = build_pitch_tonnetz(), build_chord_graph()
    out = {}

    # ---- G1
    tri = [t for t in combinations(g1.nodes, 3)
           if all(g1.has_edge(a, b) for a, b in combinations(t, 2))]
    triads = {triad_notes(r, q) for r in range(12) for q in ("maj", "min")}
    tri_sets = {frozenset(t) for t in tri}
    out["G1"] = {
        "nodes": g1.number_of_nodes(),
        "edges": g1.number_of_edges(),
        "degrees": sorted(set(dict(g1.degree).values())),
        "edges_by_interval": {lab: sum(1 for *_, d in g1.edges(data=True) if d["interval"] == lab)
                              for lab in INTERVALS.values()},
        "triangles_total": len(tri),
        "triangles_that_are_major_minor_triads": len(tri_sets & triads),
        "other_triangles": sorted("-".join(NOTE_NAMES[p] for p in sorted(t)) for t in tri_sets - triads),
        "euler_characteristic_V-E+F": g1.number_of_nodes() - g1.number_of_edges() + 24,
        "diameter": nx.diameter(g1),
        "eccentricities": sorted(set(nx.eccentricity(g1).values())),
        "not_adjacent_to_C": [NOTE_NAMES[n] for n in g1.nodes if n != 0 and not g1.has_edge(0, n)],
    }

    # ---- G2
    c_major = (0, "maj")
    dist_from_c = nx.single_source_shortest_path_length(g2, c_major)
    by_dist = {}
    for node, d in dist_from_c.items():
        by_dist.setdefault(d, []).append(triad_name(*node))
    all_d = [d for s, lengths in nx.all_pairs_shortest_path_length(g2) for t, d in lengths.items() if s != t]
    lr = cycles_from_ops(g2, "L", "R")
    out["G2"] = {
        "nodes": g2.number_of_nodes(),
        "edges": g2.number_of_edges(),
        "degrees": sorted(set(dict(g2.degree).values())),
        "edges_by_op": {op: sum(1 for *_, d in g2.edges(data=True) if d["op"] == op) for op in "PLR"},
        "bipartite_major_vs_minor": nx.is_bipartite(g2),
        "diameter": nx.diameter(g2),
        "radius": nx.radius(g2),
        "eccentricities": sorted(set(nx.eccentricity(g2).values())),
        "girth": nx.girth(g2),
        "mean_distance": sum(all_d) / len(all_d),
        "chords_by_distance_from_C": {d: sorted(v) for d, v in sorted(by_dist.items())},
        "independent_cycles_E-V+1": g2.number_of_edges() - g2.number_of_nodes() + 1,
        "PL_cycles(hexatonic)": [[triad_name(*n) for n in c] for c in cycles_from_ops(g2, "P", "L")],
        "PR_cycles(octatonic)": [[triad_name(*n) for n in c] for c in cycles_from_ops(g2, "P", "R")],
        "LR_cycle": [[triad_name(*n) for n in c] for c in lr],
        "LR_cycle_is_hamiltonian": len(lr) == 1 and len(lr[0]) == 24,
        "hamiltonian_cycles_total": count_hamiltonian_cycles(g2),
        "example_paths": {
            "C->Am": op_path(g2, (0, "maj"), (9, "min")),
            "C->G": op_path(g2, (0, "maj"), (7, "maj")),
            "C->F": op_path(g2, (0, "maj"), (5, "maj")),
            "G->Am": op_path(g2, (7, "maj"), (9, "min")),
            "C->D": op_path(g2, (0, "maj"), (2, "maj")),
        },
    }
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(structural_report(), indent=2))
