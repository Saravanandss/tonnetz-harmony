"""
Builds the data for the class demo page: for a few songs, every chord with its notes,
and for every chord change the Tonnetz distance and P/L/R path.

    python demo_data.py data/beatles output/demo_songs.json
"""
import json
import sys
from collections import Counter

import networkx as nx

from beatles import load_songs
from play_chords import chord_notes
from tonnetz import build_chord_graph, triad_name

SONGS = [
    ("02_-_Eleanor_Rigby", "Eleanor Rigby", "Revolver, 1966"),
    ("01_-_Help!", "Help!", "Help!, 1965"),
    ("03_-_Anna_(Go_To_Him)", "Anna (Go to Him)", "Please Please Me, 1963"),
    ("07_-_Here_Comes_The_Sun", "Here Comes the Sun", "Abbey Road, 1969"),
    ("02_-_Norwegian_Wood_(This_Bird_Has_Flown)", "Norwegian Wood", "Rubber Soul, 1965"),
    ("14_-_Tomorrow_Never_Knows", "Tomorrow Never Knows", "Revolver, 1966"),
]

g2 = build_chord_graph()
songs = {s["name"]: s for s in load_songs(sys.argv[1])}
out = []
for key, title, album in SONGS:
    s = songs[key]
    events, prev, hist = [], None, Counter()
    for c in s["chords"]:
        root, quality = c["chord"]
        bass, notes = chord_notes(c["raw"])
        e = {"t0": round(c["start"], 3), "t1": round(c["end"], 3), "label": c["raw"],
             "root": root, "q": quality, "notes": [bass] + notes}
        if quality != "other":
            e["name"] = triad_name(root, quality)
        if prev is not None and prev != c["chord"]:
            if prev[1] != "other" and quality != "other":
                path = nx.shortest_path(g2, prev, c["chord"])
                ops = [g2.edges[a, b]["op"] for a, b in zip(path, path[1:])]
                e["chg"] = {"from": triad_name(*prev), "d": len(ops), "ops": ops,
                            "via": [triad_name(*n) for n in path[1:-1]]}
                hist[len(ops)] += 1
        prev = c["chord"]
        events.append(e)
    n = sum(hist.values())
    out.append({
        "title": title, "album": album, "events": events,
        "changes": n,
        "triads": len({(e["root"], e["q"]) for e in events if e["q"] != "other"}),
        "hist": [hist.get(d, 0) for d in range(1, 6)],
        "mean": round(sum(d * k for d, k in hist.items()) / n, 2),
        "one": round(100 * hist.get(1, 0) / n),
        "two": round(100 * (hist.get(1, 0) + hist.get(2, 0)) / n),
    })
    print(title, n, out[-1]["triads"], out[-1]["mean"], out[-1]["one"], out[-1]["two"], out[-1]["hist"], len(events))
json.dump(out, open(sys.argv[2], "w"), separators=(",", ":"))
