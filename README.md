# Tonnetz project code

Requires Python 3.9+ with `networkx` and `matplotlib` (`pip install networkx matplotlib`).

## Run

    python tonnetz.py                              # builds G1 and G2, prints the structural checks
    python beatles.py data/beatles output          # loads the Beatles chords, builds G3, writes output/
    python figures.py output/results.json output   # draws Figure 1 and Figure 2

## Data

`data/beatles/` is the extracted "The Beatles Annotations" archive from Isophonics
(http://isophonics.net/content/reference-annotations-beatles, also in the
https://github.com/c4dm/isophonics.net repository under files/annotations/).
Only the `chordlab` and `keylab` folders are used.

## Output

- `results.json`                      every number used in the progress report
- `beatles_progression_graph.graphml` G3, opens in Gephi or `networkx.read_graphml`
- `key_relative_transitions.csv`      chord changes in major keys as Roman numerals
- `load_tonnetz.cypher`               loads G1, G2 and G3 into Neo4j (not yet run against a database)
- `fig1_tonnetz.png`, `fig2_beatles_chords.png`

The shuffled baseline uses a fixed random seed (7), so results are reproducible.

## Class demo

    python demo_data.py data/beatles output/demo_songs.json   # chords, notes and Tonnetz distances for six songs

`tonnetz_chord_walk.html` is the demo page built from that file. It plays each song's chords
and lights the current triangle on the Tonnetz. Open it in a browser.
