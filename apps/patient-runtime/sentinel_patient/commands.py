"""Voice commands "repeat" and "slower" (VC-07). Rule-based only: no model call.

`detect_command(transcript)` returns "repeat" or "slower" only when the whole utterance is the command: the command
phrases are taken out and every word left must be a filler ("eh", "please", "can you", "dear", ...). So
"it repeats every morning", "I've been slower walking" and "the rash came back again" are answers, not commands.
When both are asked for, "slower" wins (saying it slower repeats it).

Privacy: nothing here logs, prints or stores text.
"""

from __future__ import annotations

import re

COMMANDS = ("repeat", "slower")
MAX_WORDS = 14

_REPEAT_RE = re.compile(
    r"\b(?:repeat|say\s+(?:that|it|this|the\s+question)?\s*again|again|pardon|come\s+again|one\s+more\s+time|"
    r"once\s+more|what\s+did\s+you\s+say|(?:i\s+)?(?:didn't|did\s+not)\s+(?:catch|hear|get)\s+(?:that|it|you))\b")
_SLOWER_RE = re.compile(
    r"\b(?:slower|slow\s+(?:it\s+)?down|(?:more\s+)?slowly|too\s+fast|not\s+so\s+fast)\b")
_FILLERS = frozenset("""
    eh huh oh ah um uh er erm hmm mm hey well so ok okay yes yeah sorry pardon please thanks thank
    dear love darling sweetheart dearie nurse
    can could would will you u me i say said tell ask read go speak talk it that this the question a an bit little
    just again more much once there now what was for if do did mind be possible kindly way your and then very really
    """.split())


def detect_command(transcript: str) -> str | None:
    """"repeat", "slower" or None. Case and punctuation are ignored."""
    text = (transcript or "").lower().replace("’", "'").replace("‘", "'")
    text = " ".join(re.sub(r"[^\w']+", " ", text).split())
    if not text or len(text.split()) > MAX_WORDS:
        return None
    slower = _SLOWER_RE.search(text) is not None
    repeat = _REPEAT_RE.search(text) is not None
    if not (slower or repeat):
        return None
    rest = _REPEAT_RE.sub(" ", _SLOWER_RE.sub(" ", text)).split()
    if any(word not in _FILLERS for word in rest):
        return None
    return "slower" if slower else "repeat"
