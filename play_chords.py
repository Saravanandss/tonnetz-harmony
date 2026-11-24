"""
Turn an Isophonics chord .lab file into audio, so you can hear the progression.

    python play_chords.py path/to/song.lab output.wav

Each chord is played as plain notes (bass note + chord tones) at the times given in the file.
"""
import re
import sys
import wave

import numpy as np

RATE = 22050
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
DEGREE = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 9: 14, 11: 17, 13: 21}
SHORTHAND = {
    "": [0, 4, 7], "maj": [0, 4, 7], "min": [0, 3, 7], "dim": [0, 3, 6], "aug": [0, 4, 8],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "maj6": [0, 4, 7, 9],
    "min6": [0, 3, 7, 9], "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "min9": [0, 3, 7, 10, 14],
    "sus4": [0, 5, 7], "sus2": [0, 2, 7], "dim7": [0, 3, 6, 9], "hdim7": [0, 3, 6, 10],
    "minmaj7": [0, 3, 7, 11],
}


def pitch_class(name):
    return (LETTER_PC[name[0]] + name.count("#") - name.count("b")) % 12


def degree(text):
    """'b7' -> 10 semitones, '#9' -> 15, '3' -> 4."""
    number = int(text.lstrip("b#"))
    return DEGREE[number] + text.count("#") - text.count("b")


def chord_notes(label):
    """Chord label -> (bass MIDI note, list of chord MIDI notes), or None for 'N'."""
    if label in ("N", "X"):
        return None
    m = re.match(r"^([A-G][b#]*)(?::([a-z0-9]*)(?:\(([^)]*)\))?)?(?:/(.+))?$", label)
    root = pitch_class(m.group(1))
    shorthand, extras, bass = m.group(2) or "", m.group(3) or "", m.group(4)
    if shorthand == "" and extras and ":" in label:
        intervals = []                                   # explicit list such as C:(1,5)
    else:
        intervals = list(SHORTHAND[shorthand])
    for extra in [e.strip() for e in extras.split(",") if e.strip()]:
        if extra.startswith("*"):
            intervals = [i for i in intervals if i % 12 != degree(extra[1:]) % 12]
        else:
            intervals.append(degree(extra))
    bass_pc = (root + (degree(bass) if bass else 0)) % 12
    bass_note = 36 + bass_pc if bass_pc >= 4 else 48 + bass_pc           # E2 .. Eb3
    notes = []
    for i in sorted(set(intervals)):
        note = 48 + (root + i) % 12 if i < 12 else 60 + (root + i) % 12
        while note < 52:                                  # keep the chord in a mid register
            note += 12
        notes.append(note)
    return bass_note, notes


def tone(midi, seconds, volume):
    """A plucked, piano-like note: a few harmonics with a decaying envelope."""
    t = np.arange(int(seconds * RATE)) / RATE
    freq = 440.0 * 2 ** ((midi - 69) / 12)
    wave_ = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)))
    envelope = np.exp(-t * 2.2) * np.minimum(1, t / 0.008)
    fade = np.minimum(1, (seconds - t) / 0.03)
    return volume * wave_ * envelope * fade


def render(lab_path, out_path, pulse=0.93):
    rows = [line.split() for line in open(lab_path) if line.strip()]
    total = float(rows[-1][1])
    audio = np.zeros(int(total * RATE) + RATE)
    for start, end, label in rows:
        start, end = float(start), float(end)
        parsed = chord_notes(label)
        if parsed is None:
            continue
        bass, notes = parsed
        length = end - start
        hits = max(1, round(length / pulse))              # re-strike long chords so they don't die away
        for h in range(hits):
            t0 = start + h * length / hits
            dur = min(end + 0.25, t0 + length / hits + 0.35) - t0
            i0 = int(t0 * RATE)
            for k, note in enumerate([bass] + notes):
                vol = (0.5 if k == 0 else 0.28) * (1.0 if h == 0 else 0.7)
                offset = int(k * 0.012 * RATE)            # slight strum
                seg = tone(note, dur, vol)
                audio[i0 + offset:i0 + offset + len(seg)] += seg[:len(audio) - i0 - offset]
    audio = audio / np.abs(audio).max() * 0.85
    with wave.open(out_path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((audio * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2])
