"""Rebuild narration audio and cue files for a video project from its narration.json.

    docs/demo-video/tools/.venv/bin/python docs/demo-video/tools/build_narration.py docs/demo-video/video-1 [s2 s3]
    (extra arguments: voice settings, e.g. --voice af_heart --speed 0.92 --split clause)

Writes assets/audio/<scene>-narration.wav plus .cues.json/.cues.js. Afterwards read the scene durations printed here
and update the host data-duration values and the root data-duration in index.html if a scene got longer or shorter.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
project = Path(sys.argv[1])
rest = sys.argv[2:]
# scene names come first; everything from the first "--" onwards is passed to narrate.py
first_flag = next((i for i, a in enumerate(rest) if a.startswith("--")), len(rest))
scenes, flags = rest[:first_flag], rest[first_flag:]
texts = json.loads((project / "narration.json").read_text())
for scene, text in texts.items():
    if scene.startswith("_") or (scenes and scene not in scenes):
        continue
    out = project / "assets" / "audio" / f"{scene}-narration.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(HERE / "narrate.py"), text, "-o", str(out), *flags], check=True,
                   stdout=subprocess.DEVNULL)
    cues = json.loads(out.with_suffix(".cues.json").read_text())
    print(f"{scene}: narration {cues['duration']:.2f} s, {len(cues['sentences'])} sentences")
