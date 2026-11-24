"""
Beatles chord progressions on the Tonnetz.

Reads the Isophonics "The Beatles Annotations" archive (chordlab + keylab folders),
reduces every chord to one of the 24 major/minor triads, builds the directed weighted
progression graph G3, and measures every chord change as a shortest-path distance on
the chord graph G2.

    python beatles.py  path/to/extracted/annotations  output_folder
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from tonnetz import NOTE_NAMES, build_chord_graph, op_path, triad_name

LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR_SHORTHANDS = {"maj", "maj7", "7", "maj6", "9", "maj9"}
MINOR_SHORTHANDS = {"min", "min7", "min6", "min9", "minmaj7"}
MINOR_MODES = {"minor", "aeolian", "dorian"}
ROMAN = ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"]


# ---------------------------------------------------------------- parsing
def pitch_class(name):
    pc = LETTER_PC[name[0]]
    for accidental in name[1:]:
        pc += 1 if accidental == "#" else -1
    return pc % 12


def reduce_chord(label):
    """
    Harte chord label -> (root, 'maj' | 'min' | 'other'), or None for 'N' (no chord).

    Sevenths, sixths and ninths are reduced to the triad underneath them.
    Chords without a major/minor third and perfect-fifth frame (dim, aug, sus,
    bare root or power chords) come back as 'other' and are counted separately.
    The bass note (after '/') is ignored.
    """
    if label in ("N", "X"):
        return None
    m = re.match(r"^([A-G][b#]*)(?::([a-z0-9]*)(?:\(([^)]*)\))?)?(?:/.*)?$", label)
    if not m:
        raise ValueError(f"cannot parse chord label {label!r}")
    root = pitch_class(m.group(1))
    has_colon = ":" in label
    shorthand = m.group(2) or ""
    extras = [x.strip() for x in (m.group(3) or "").split(",") if x.strip()]

    if "*3" in extras or "*b3" in extras:            # third explicitly removed
        return root, "other"
    if not has_colon or shorthand in MAJOR_SHORTHANDS:
        return root, "maj"
    if shorthand in MINOR_SHORTHANDS:
        return root, "min"
    if shorthand == "" and extras:                   # explicit interval list, e.g. C:(1,5)
        if "b3" in extras:
            return root, "min"
        if "3" in extras:
            return root, "maj"
    return root, "other"


def read_lab(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((float(parts[0]), float(parts[1]), parts[2:]))
    return rows


def read_keys(path):
    """[(start, end, tonic_pc, 'major'|'minor')] from a keylab file."""
    keys = []
    for start, end, rest in read_lab(path):
        if rest[0] != "Key" or len(rest) < 2:
            continue
        tonic, _, mode = rest[1].partition(":")
        keys.append((start, end, pitch_class(tonic), "minor" if mode in MINOR_MODES else "major"))
    return keys


def load_songs(root):
    """One dict per song: name, album, triad sequence with times, key segments."""
    root = Path(root)
    songs = []
    for chord_file in sorted(root.glob("chordlab/The Beatles/*/*.lab")):
        key_file = root / "keylab" / chord_file.relative_to(root / "chordlab")
        chords = []
        for start, end, rest in read_lab(chord_file):
            reduced = reduce_chord(rest[0])
            if reduced is not None:
                chords.append({"start": start, "end": end, "raw": rest[0], "chord": reduced})
        songs.append({
            "album": chord_file.parent.name,
            "name": chord_file.stem,
            "chords": chords,
            "keys": read_keys(key_file) if key_file.exists() else [],
        })
    return songs


def key_at(song, t):
    for start, end, tonic, mode in song["keys"]:
        if start <= t < end:
            return tonic, mode
    return None


def chord_changes(song):
    """
    Consecutive chord pairs (u, v, time) with u != v after reduction.
    'E -> E:7/3' is therefore not a change, because both reduce to E major.
    """
    seq = []
    for c in song["chords"]:
        if not seq or seq[-1]["chord"] != c["chord"]:
            seq.append(c)
    return [(a["chord"], b["chord"], b["start"]) for a, b in zip(seq, seq[1:])]


def roman(chord, tonic):
    root, quality = chord
    numeral = ROMAN[(root - tonic) % 12]
    return numeral if quality == "maj" else numeral.lower()


# ---------------------------------------------------------------- analysis
def analyse(data_root, seed=7, shuffles=200):
    g2 = build_chord_graph()
    dist = dict(nx.all_pairs_shortest_path_length(g2))
    songs = load_songs(data_root)

    raw_labels = Counter(c["raw"] for s in songs for c in s["chords"])
    reduced_kind = Counter(c["chord"][1] for s in songs for c in s["chords"])
    other_labels = Counter(c["raw"] for s in songs for c in s["chords"] if c["chord"][1] == "other")

    # ---- G3 : directed weighted progression graph on the 24 triads
    g3 = nx.DiGraph(name="G3 Beatles progression graph")
    g3.add_nodes_from(g2.nodes(data=True))
    all_changes = triad_changes = 0
    dist_hist = Counter()
    op_hist = Counter()
    rel_trans = Counter()        # key-relative transitions, major-key passages only
    rel_time = Counter()         # key-relative chord durations, major-key passages only
    per_album = defaultdict(lambda: Counter())

    for s in songs:
        for u, v, t in chord_changes(s):
            all_changes += 1
            if u[1] == "other" or v[1] == "other":
                continue
            triad_changes += 1
            w = g3.get_edge_data(u, v, {"weight": 0})["weight"]
            g3.add_edge(u, v, weight=w + 1)
            d = dist[u][v]
            dist_hist[d] += 1
            per_album[s["album"]][d] += 1
            if d == 1:
                op_hist[g2.edges[u, v]["op"]] += 1
            key = key_at(s, t)
            if key and key[1] == "major":
                rel_trans[(roman(u, key[0]), roman(v, key[0]))] += 1
        for c in s["chords"]:
            key = key_at(s, c["start"])
            if key and key[1] == "major" and c["chord"][1] != "other":
                rel_time[roman(c["chord"], key[0])] += c["end"] - c["start"]

    for u, v, d in g3.edges(data=True):
        d["tonnetz_distance"] = dist[u][v]

    def mean(hist):
        return sum(d * n for d, n in hist.items()) / sum(hist.values())

    # ---- baseline 1: every ordered pair of different triads equally likely
    uniform = Counter(dist[u][v] for u in g2 for v in g2 if u != v)

    # ---- baseline 2: keep each song's chords, shuffle their order
    rng = random.Random(seed)
    shuffled = Counter()
    for _ in range(shuffles):
        for s in songs:
            seq = [c["chord"] for c in s["chords"] if c["chord"][1] != "other"]
            rng.shuffle(seq)
            for a, b in zip(seq, seq[1:]):
                if a != b:
                    shuffled[dist[a][b]] += 1

    def shares(hist):
        total = sum(hist.values())
        return {d: hist.get(d, 0) / total for d in range(1, 6)}

    # ---- most common transitions (absolute pitch and key-relative)
    top_abs = sorted(g3.edges(data=True), key=lambda e: -e[2]["weight"])[:15]
    in_major = sum(rel_trans.values())
    rel_d = {}
    for (a, b), n in rel_trans.items():
        rel_d[(a, b)] = n

    # ---- research question 2: do the most used chords sit together on the Tonnetz?
    total_time = sum(rel_time.values())
    ranked = sorted(rel_time.items(), key=lambda kv: -kv[1])
    numeral_to_node = {roman((r, q), 0): (r, q) for r in range(12) for q in ("maj", "min")}
    cluster = {}
    for k in (4, 6, 8):
        top_nodes = [numeral_to_node[name] for name, _ in ranked[:k]]
        pairs = [(a, b) for i, a in enumerate(top_nodes) for b in top_nodes[i + 1:]]
        observed = sum(dist[a][b] for a, b in pairs) / len(pairs)
        sub = g2.subgraph(top_nodes)
        rnd = []
        nodes = list(g2.nodes)
        for _ in range(20000):
            pick = rng.sample(nodes, k)
            pp = [(a, b) for i, a in enumerate(pick) for b in pick[i + 1:]]
            rnd.append(sum(dist[a][b] for a, b in pp) / len(pp))
        cluster[k] = {
            "chords": [name for name, _ in ranked[:k]],
            "share_of_playing_time": sum(t for _, t in ranked[:k]) / total_time,
            "mean_pairwise_distance": observed,
            "random_sets_mean": sum(rnd) / len(rnd),
            "random_sets_share_as_compact_or_more": sum(1 for x in rnd if x <= observed) / len(rnd),
            "connected_components_in_G2": nx.number_connected_components(sub),
        }

    results = {
        "songs": len(songs),
        "albums": len({s["album"] for s in songs}),
        "chord_segments": sum(len(s["chords"]) for s in songs),
        "distinct_raw_chord_labels": len(raw_labels),
        "segments_by_reduced_kind": dict(reduced_kind),
        "share_segments_reduced_to_triads":
            (reduced_kind["maj"] + reduced_kind["min"]) / sum(reduced_kind.values()),
        "top_non_triad_labels": other_labels.most_common(8),
        "chord_changes_all": all_changes,
        "chord_changes_between_two_triads": triad_changes,
        "G3": {
            "nodes": g3.number_of_nodes(),
            "nodes_used": sum(1 for n in g3 if g3.degree(n) > 0),
            "edges": g3.number_of_edges(),
            "possible_edges": 24 * 23,
            "total_weight": int(g3.size(weight="weight")),
            "edges_that_are_also_G2_edges": sum(1 for u, v in g3.edges if g2.has_edge(u, v)),
        },
        "distance_counts": {d: dist_hist.get(d, 0) for d in range(1, 6)},
        "distance_shares_observed": shares(dist_hist),
        "distance_shares_uniform": shares(uniform),
        "distance_shares_shuffled": shares(shuffled),
        "mean_distance_observed": mean(dist_hist),
        "mean_distance_uniform": mean(uniform),
        "mean_distance_shuffled": mean(shuffled),
        "single_step_ops": dict(op_hist),
        "top_transitions_absolute": [
            {"from": triad_name(*u), "to": triad_name(*v), "count": d["weight"],
             "distance": d["tonnetz_distance"], "path": op_path(g2, u, v)}
            for u, v, d in top_abs],
        "major_key_transitions": in_major,
        "top_transitions_key_relative": [
            {"from": a, "to": b, "count": n, "share": n / in_major,
             "distance": dist[numeral_to_node[a]][numeral_to_node[b]],
             "path": op_path(g2, numeral_to_node[a], numeral_to_node[b])}
            for (a, b), n in sorted(rel_trans.items(), key=lambda kv: -kv[1])[:12]],
        "chord_time_shares_key_relative": [(name, t / total_time) for name, t in ranked[:10]],
        "cluster_test": cluster,
        "mean_distance_by_album": {a: round(mean(h), 3) for a, h in sorted(per_album.items())},
        "changes_by_album": {a: sum(h.values()) for a, h in sorted(per_album.items())},
    }
    return g2, g3, results, rel_trans


def write_cypher(g1, g2, g3, path):
    """Cypher script that loads the three graphs into Neo4j."""
    lines = ["// Tonnetz project - load script for Neo4j", "// Run in Neo4j Browser or with cypher-shell.", "",
             "CREATE CONSTRAINT pitch_pc IF NOT EXISTS FOR (p:Pitch) REQUIRE p.pc IS UNIQUE;",
             "CREATE CONSTRAINT triad_name IF NOT EXISTS FOR (t:Triad) REQUIRE t.name IS UNIQUE;", "",
             "// G1 : pitch-class Tonnetz"]
    for pc, d in g1.nodes(data=True):
        lines.append(f"MERGE (:Pitch {{pc: {pc}, name: '{d['name']}'}});")
    for a, b, d in g1.edges(data=True):
        lines.append(f"MATCH (a:Pitch {{pc: {a}}}), (b:Pitch {{pc: {b}}}) "
                     f"MERGE (a)-[:INTERVAL {{type: '{d['interval']}'}}]->(b);")
    lines += ["", "// G2 : chord graph (triads joined by P / L / R)"]
    for (root, quality), d in g2.nodes(data=True):
        lines.append(f"MERGE (:Triad {{name: '{d['name']}', root: {root}, quality: '{quality}', "
                     f"notes: {d['notes']}}});")
    for (root, quality), d in g2.nodes(data=True):
        for pc in d["notes"]:
            lines.append(f"MATCH (t:Triad {{name: '{d['name']}'}}), (p:Pitch {{pc: {pc}}}) "
                         f"MERGE (t)-[:HAS_NOTE]->(p);")
    for a, b, d in g2.edges(data=True):
        lines.append(f"MATCH (a:Triad {{name: '{triad_name(*a)}'}}), (b:Triad {{name: '{triad_name(*b)}'}}) "
                     f"MERGE (a)-[:PLR {{op: '{d['op']}'}}]->(b);")
    lines += ["", "// G3 : observed Beatles chord changes"]
    for a, b, d in g3.edges(data=True):
        lines.append(f"MATCH (a:Triad {{name: '{triad_name(*a)}'}}), (b:Triad {{name: '{triad_name(*b)}'}}) "
                     f"MERGE (a)-[:NEXT {{count: {d['weight']}, distance: {d['tonnetz_distance']}}}]->(b);")
    lines += ["", "// Example: smoothest route between two chords",
              "// MATCH p = shortestPath((:Triad {name:'C'})-[:PLR*]-(:Triad {name:'Am'}))",
              "// RETURN [r IN relationships(p) | r.op];", ""]
    Path(path).write_text("\n".join(lines))


if __name__ == "__main__":
    from tonnetz import build_pitch_tonnetz

    data_root = sys.argv[1] if len(sys.argv) > 1 else "data/beatles"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "output")
    out.mkdir(parents=True, exist_ok=True)

    g2, g3, results, rel_trans = analyse(data_root)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    write_cypher(build_pitch_tonnetz(), g2, g3, out / "load_tonnetz.cypher")

    export = nx.DiGraph()
    for n, d in g3.nodes(data=True):
        export.add_node(d["name"])
    for u, v, d in g3.edges(data=True):
        export.add_edge(triad_name(*u), triad_name(*v), **d)
    nx.write_graphml(export, out / "beatles_progression_graph.graphml")
    with open(out / "key_relative_transitions.csv", "w") as f:
        f.write("from,to,count\n")
        for (a, b), n in sorted(rel_trans.items(), key=lambda kv: -kv[1]):
            f.write(f"{a},{b},{n}\n")
    print(json.dumps(results, indent=2))
