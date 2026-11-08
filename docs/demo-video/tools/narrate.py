"""Pause-controlled Kokoro narration (prototype).

Splits text into chunks at punctuation, synthesizes each chunk with the Heart+Nicole blend, and inserts a fixed
silence after each chunk that depends on the punctuation that ended it. `--split sentence` keeps commas inside the
sentence (the model sets the comma pauses); `--split clause` also cuts at commas, colons and dashes so every pause
is ours. `[pause 1.2]` in the text adds an explicit pause in seconds.

Also writes `<name>.cues.json` and `<name>.cues.js` (sentence start and end times; the .js sets `window.NARRATION_<SCENE>`,
e.g. `s2-narration.wav` gives `window.NARRATION_S2`). Scenes load the .js and place
their beats from it, so changing the voice, speed or pauses and re-running this tool re-times the scene.

    python narrate.py "Walter is ninety-two. ..." -o assets/audio/s1-narration.wav [--voice af_heart --speed 0.92]
"""
import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASE = str(Path.home() / ".cache/hyperframes/tts") + "/"
PAUSE = {",": 0.30, ";": 0.40, ":": 0.40, "-": 0.35, "—": 0.35, ".": 0.60, "?": 0.65, "!": 0.60, "…": 0.90, "\n": 1.0}
HEAD, TAIL = 0.0, 0.0

def chunks(text, split):
    text = text.replace("...", "…")
    seps = r"[.?!…\n]" if split == "sentence" else r"[,;:.?!…—\n]"
    out, buf = [], ""
    for part in re.split(rf"(\[pause [0-9.]+\]|{seps})", text):
        if part is None or part == "":
            continue
        m = re.fullmatch(r"\[pause ([0-9.]+)\]", part)
        if m:
            if buf.strip():
                out.append((buf.strip(), "."))
                buf = ""
            out.append((None, float(m.group(1))))
        elif re.fullmatch(seps, part):
            # keep the mark so the model hears the intonation (comma = continue, period = fall)
            mark = "." if part == "\n" else part
            if buf.strip():
                out.append((buf.strip() + ("" if part == "\n" else mark), part))
            buf = ""
        else:
            buf += part
    if buf.strip():
        out.append((buf.strip(), "."))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text"); ap.add_argument("-o", required=True)
    ap.add_argument("--split", choices=["sentence", "clause"], default="sentence")
    ap.add_argument("--speed", type=float, default=0.95)
    ap.add_argument("--scale", type=float, default=1.0, help="multiply every pause")
    ap.add_argument("--voice", default="heart_nicole",
                    help="heart_nicole (60/40 blend, the locked voice) or any Kokoro voice id, e.g. af_heart")
    a = ap.parse_args()
    k = Kokoro(BASE + "models/kokoro-v1.0.onnx", BASE + "voices/voices-v1.0.bin")
    voice = (k.get_voice_style("af_heart") * 0.6 + k.get_voice_style("af_nicole") * 0.4
             if a.voice == "heart_nicole" else a.voice)
    sr, pieces, log = 24000, [], []
    cursor = 0.0                      # seconds written so far
    sentences, current = [], None     # cue file: where each sentence starts and ends (speech only, not the pause)
    for text, mark in chunks(a.text, a.split):
        if text is None:
            gap = mark * a.scale
            pieces.append(np.zeros(int(sr * gap))); cursor += gap; log.append(f"explicit pause {mark}s"); continue
        audio, sr = k.create(text, voice=voice, speed=a.speed, lang="en-us")
        loud = np.flatnonzero(np.abs(audio) > 0.01)  # drop the model's own lead/trail silence; our gaps are exact
        if loud.size:
            audio = audio[max(loud[0] - int(sr * 0.02), 0): loud[-1] + int(sr * 0.04)]
        piece = np.concatenate([np.zeros(int(sr * HEAD)), audio, np.zeros(int(sr * TAIL))])
        pieces.append(piece)
        start, end = cursor, cursor + len(piece) / sr
        if current is None:
            current = {"text": text, "start": round(start, 3), "end": round(end, 3)}
        else:
            current["text"] += " " + text
            current["end"] = round(end, 3)
        cursor = end
        gap = PAUSE.get(mark, 0.5) * a.scale
        pieces.append(np.zeros(int(sr * gap))); cursor += gap
        if mark in (".", "?", "!", "…", "\n"):  # a sentence is over; commas and colons stay inside it
            sentences.append(current); current = None
        log.append(f"{text[:40]!r:44} +{gap:.2f}s ({mark!r})")
    if current is not None:
        sentences.append(current)
    wav = np.concatenate(pieces)
    sf.write(a.o, wav, sr)
    # Cue file next to the wav: scenes read it, so a different voice, speed or pause setting re-times the beats.
    out = Path(a.o)
    cues = {"voice": a.voice, "speed": a.speed, "pause_scale": a.scale, "split": a.split,
            "duration": round(len(wav) / sr, 3),
            "sentences": [{"i": i, **s} for i, s in enumerate(sentences)]}
    out.with_suffix(".cues.json").write_text(json.dumps(cues, indent=2) + "\n")
    # one global per scene file so several scenes can load their cues side by side: s2-narration.wav -> NARRATION_S2
    name = "NARRATION_" + re.sub(r"[^A-Z0-9]+", "_", re.sub(r"[-_]?narration$", "", out.stem, flags=re.I).upper()).strip("_")
    out.with_suffix(".cues.js").write_text(f"window.{name} = " + json.dumps(cues) + ";\n")
    print("\n".join(log)); print(f"total {len(wav)/sr:.1f}s, {len(sentences)} sentences -> {out.with_suffix('.cues.json').name}")

if __name__ == "__main__":
    main()
