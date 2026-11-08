"""Answer rating and relevant-part extraction (VC-04, VC-06). Local model plus simple rules; no cloud AI.

`rate_answer(question, ask, filtered_text)` rates one answer to one survey question (D-017:
`{question_id, purpose, asks[0..2]}`) as one of `answer_rating` in schema/enums.json:
- complete: answers what was asked;
- partial: on topic but missing what was asked (a symptom but no level for a severity question; "maybe");
- off_topic: answers something else;
- rambling: a long reply where the answer is buried among unrelated talk (`relevant_text` holds the answer);
- no_answer: empty, silence, "I don't know", "pardon?", "what?".

Rules run first and override the model (Scoping Doc 17.1); the model is skipped whenever a rule decides:
1. empty or only filler / "don't know" / "pardon?" -> no_answer;
2. long answers (more than LONG_WORDS words): split into sentences and mark each one on topic by the rules below.
   Some on topic and the rest is a large share of the words -> rambling, keeping the on-topic sentences; all on
   topic -> complete;
3. short answers, by purpose: severity -> `severity_in_text` gives a level; onset -> `onset_in_text` gives a range;
   adherence -> a clear yes / no or "I took it" / "I forgot"; symptom_screen -> a symptom word (or "no",
   "nothing"); wellbeing -> a feeling word; any yes-or-no ask -> a clear yes / no; a choice ask (asks[2]) -> one
   of the listed choices. A bare "yes" where the question also needs "what" -> partial; only a hedge ("maybe",
   "sort of") -> partial.
Otherwise the local model (Ollama, loopback only, temperature 0, JSON-schema output
`{rating, relevant_sentences: [indices]}`) judges the numbered sentences. Python validates the result: unknown
ratings fall back to the rules, bad indices are dropped, `relevant_text` is always whole sentences copied from the
input (never model text), and the length rules still apply (a long answer the model calls complete but only
partly quotes is rambling; a short one cannot be rambling).

Model problems never raise: the rules decide alone (source "rules_fallback"). Nothing here logs or prints text or
model output. The Ollama client is `extract._default_client` (proxies and redirects off, loopback host only).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sentinel_patient import extract
from sentinel_patient.extract import ollama_host, ollama_model, onset_in_text, severity_in_text

RATINGS = ("complete", "partial", "off_topic", "rambling", "no_answer")  # schema/enums.json answer_rating
COMPLETE, PARTIAL, OFF_TOPIC, RAMBLING, NO_ANSWER = RATINGS
SOURCE_RULES, SOURCE_MODEL, SOURCE_FALLBACK = "rules", "model", "rules_fallback"

LONG_WORDS = 40          # more words than this (or several sentences, see _is_long) can be rambling
SHORT_WORDS = 20         # this many words or fewer can never be rambling
OFF_TOPIC_SHARE = 0.4    # a long answer is rambling when at least this share of its words is off topic
MAX_SENTENCES = 40       # sentences shown to the model (the rest are never quoted)


@dataclass(frozen=True)
class Rating:
    rating: str          # one of RATINGS
    relevant_text: str   # whole sentences copied from the answer; "" for off_topic / no_answer
    source: str          # "rules" | "model" | "rules_fallback"


def rate_answer(question: Mapping, ask: int, filtered_text: str, *, client: Any = None) -> Rating:
    """Rate `filtered_text` (already passed through `filter.redact`) as an answer to `question["asks"][ask]`.

    `ask`: 0 = first ask, 1 = simpler words, 2 = choices or yes / no. `client`: anything with
    `.chat(model=..., messages=..., format=..., options=...)` returning a mapping whose `["message"]["content"]`
    is the JSON string; defaults to the loopback Ollama client. Never raises for model problems.
    """
    purpose = str(question.get("purpose") or "") if isinstance(question, Mapping) else ""
    ask, ask_text = _ask(question, ask)
    text = extract._normalise(filtered_text or "")
    sentences = split_sentences(text)

    decided = _rules(purpose, ask, ask_text, text, sentences)
    if decided is not None:
        return Rating(decided[0], decided[1], SOURCE_RULES)

    try:
        host, model = ollama_host(), ollama_model()
        if client is None:
            client = extract._default_client(host)
        response = client.chat(model=model, messages=_messages(purpose, ask_text, sentences),
                               format=output_schema(), options={"temperature": 0})
        parsed = _parse(response)
    except Exception:  # noqa: BLE001 - any model / config problem: the rules decide alone (message not kept)
        parsed = None
    if parsed is None:
        rating, relevant = _fallback(purpose, ask, ask_text, text, sentences)
        return Rating(rating, relevant, SOURCE_FALLBACK)
    rating, relevant = _validate(parsed, purpose, ask, ask_text, text, sentences)
    return Rating(rating, relevant, SOURCE_MODEL)


# --- Sentences ----------------------------------------------------------------------------------------------------
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])[\"')\]]*\s+|\n+")
_CLAUSE_RE = re.compile(r"(?<=[;,])\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
LONG_SENTENCE_WORDS = 30  # an unpunctuated run longer than this is split again at commas and semicolons


def split_sentences(text: str) -> list[str]:
    """Sentences of `text`, each an exact substring (stripped). Very long unpunctuated runs (speech-to-text
    without full stops) are split again at commas and semicolons."""
    out = []
    for part in _SENTENCE_END_RE.split(text or ""):
        part = part.strip()
        if not part:
            continue
        if _word_count(part) > LONG_SENTENCE_WORDS:
            out.extend(p.strip() for p in _CLAUSE_RE.split(part) if p.strip())
        else:
            out.append(part)
    return out


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _join(sentences: list[str]) -> str:
    return " ".join(sentences)


def _ask(question: Any, ask: Any) -> tuple[int, str]:
    """(ask index, ask text); an index outside the question's asks counts as the first ask."""
    asks = question.get("asks") if isinstance(question, Mapping) else None
    if not isinstance(asks, (list, tuple)) or not asks:
        return 0, ""
    index = ask if isinstance(ask, int) and not isinstance(ask, bool) and 0 <= ask < len(asks) else 0
    value = asks[index]
    return index, value if isinstance(value, str) else ""


# --- Vocabulary ---------------------------------------------------------------------------------------------------
def _phrases(*items: str) -> re.Pattern:
    alternatives = "|".join(sorted(items, key=len, reverse=True))
    return re.compile(rf"(?<![\w'])(?:{alternatives})(?![\w'])", re.IGNORECASE)


_FILLER_RE = _phrases(r"um+", r"uh+m*", r"e+r+m*", r"h+m+", r"m+h*m+", r"a+h+", r"o+h+", r"well", r"so", r"like",
                      r"okay so", r"ok so", r"anyway", r"you know", r"i mean", r"hello", r"hi", r"hey",
                      r"let me think", r"let me see", r"(?:i'?m\s+|i\s+am\s+)?trying\s+to\s+(?:think|remember)",
                      r"good question", r"ha", r"haha", r"oh dear", r"gosh",
                      r"thanks?", r"thank you", r"please", r"and", r"just", r"actually", r"honestly")
_NO_ANSWER_RE = _phrases(
    r"i\s+(?:really\s+)?(?:don'?t|do\s+not|dont)\s+know", r"(?:don'?t|dont)\s+know", r"dunno", r"no\s+idea",
    r"(?:i'?m\s+|i\s+am\s+)?not\s+(?:really\s+)?sure", r"(?:i\s+)?(?:can'?t|cannot|don'?t)\s+(?:remember|recall|say)",
    r"pardon(?:\s+me)?", r"what", r"huh", r"eh", r"sorry", r"i'?m\s+sorry", r"excuse\s+me", r"come\s+again",
    r"(?:can|could|would)\s+you\s+(?:please\s+)?(?:repeat|say)\s+(?:that|it|the\s+question)(?:\s+again)?",
    r"(?:please\s+)?(?:repeat|say)\s+(?:that|it|the\s+question)(?:\s+again)?(?:\s+please)?",
    r"(?:i\s+)?(?:didn'?t|did\s+not)\s+(?:catch|hear|get|understand)\s+(?:that|you|it|the\s+question)",
    r"what\s+(?:do\s+you\s+mean|was\s+the\s+question|did\s+you\s+say)", r"skip(?:\s+(?:it|this|that))?",
    r"pass", r"next(?:\s+question)?", r"no\s+comment", r"rather\s+not\s+say", r"i'?d\s+rather\s+not\s+say",
    r"who\s+knows", r"hard\s+to\s+say", r"not\s+a\s+clue")
_HEDGE_RE = _phrases(r"maybe", r"perhaps", r"possibly", r"probably", r"sort\s+of", r"kind\s+of", r"kinda", r"sorta",
                     r"i\s+guess", r"i\s+suppose", r"i\s+think\s+so", r"i\s+think", r"more\s+or\s+less",
                     r"it\s+depends", r"sometimes", r"a\s+bit", r"a\s+little", r"somewhat", r"not\s+really\s+sure",
                     r"could\s+be", r"might\s+be", r"might\s+have", r"i\s+might\s+have", r"on\s+and\s+off",
                     r"so\s+so", r"so-so", r"yes\s+and\s+no")
_YES_RE = _phrases(r"yes", r"yeah", r"yea", r"yep", r"yup", r"ya", r"aye", r"sure", r"definitely", r"absolutely",
                   r"certainly", r"correct", r"of\s+course", r"uh[\s-]?huh", r"mhm", r"i\s+did", r"i\s+have",
                   r"i\s+do", r"i\s+was", r"it\s+is", r"it\s+does", r"it\s+did", r"it\s+was", r"that'?s\s+right",
                   r"yes\s+please", r"i\s+have\s+done", r"done", r"took\s+(?:it|them)", r"i\s+took\s+(?:it|them)")
_NO_RE = _phrases(r"no", r"nope", r"nah", r"not\s+really", r"not\s+at\s+all", r"never", r"none", r"nothing",
                  r"i\s+(?:didn'?t|did\s+not|haven'?t|have\s+not|don'?t|do\s+not|wasn'?t|was\s+not)",
                  r"it\s+(?:didn'?t|did\s+not|isn'?t|is\s+not|wasn'?t|was\s+not|doesn'?t|does\s+not)",
                  r"it'?s\s+not", r"not\s+yet", r"no\s+thanks?", r"nothing\s+new", r"not\s+that\s+i\s+know\s+of",
                  r"not\s+that\s+i\s+noticed", r"all\s+(?:good|fine|clear)")
_ADHERENCE_RE = re.compile(r"(?<![\w'])(?:took|taken|forgot|forgotten|missed|skipped|ran\s+out|stopped\s+taking)"
                           r"(?![\w'])", re.IGNORECASE)
_FEELING_RE = re.compile(
    r"(?<![\w'])(?:fine|good|great|okay|ok|alright|all\s+right|better|worse|bad|awful|terrible|horrible|rough|"
    r"poorly|unwell|sick|ill|lousy|rubbish|grotty|crap|crappy|meh|normal|myself|fantastic|brilliant|wonderful|"
    r"excellent|grand|tired|exhausted|low|down|happy|sad|anxious|stressed|nauseous|queasy|dizzy|achy|sore|"
    r"(?:feel\w*|been|doing|pretty|quite|very|not|really)\s+well|not\s+(?:great|good|bad|so\s+good|too\s+bad)|"
    r"under\s+the\s+weather|same\s+as\s+(?:usual|always|before)|no\s+(?:change|different))(?![\w'])",
    re.IGNORECASE)
_HEALTH_RE = re.compile(
    r"(?<![\w'])(?:pains?|painful\w*|hurt\w*|ache\w*|aching|sore\w*|headaches?|migraines?|nause\w*|sick|"
    r"vomit\w*|throw\w*\s+up|fever\w*|temperature|dizz\w*|faint\w*|bleed\w*|blood|bruis\w*|numb|numbness|"
    r"tingl\w*|cramp\w*|swell\w*|swollen|symptoms?|skin|nails?|feel\w*|felt)(?![\w'])", re.IGNORECASE)
_EXPOSURE_RE = re.compile(
    r"(?<![\w'])(?:new|started|starting|switched|changed|began|begun|tried|trying|bought|using|use|ate|eaten|"
    r"eating|drank|soap|cream|lotion|shampoo|detergent|washing\s+powder|perfume|makeup|food|diet|restaurant|"
    r"supplements?|vitamins?|herbal|gym|exercise|running|swimming|garden\w*|hiking|holiday|travel\w*|pets?|"
    r"dog|cat|medicine|tablets?|pills?)(?![\w'])", re.IGNORECASE)
_STOPWORDS = frozenset({
    "a", "an", "the", "it", "is", "are", "was", "were", "be", "been", "you", "your", "yours", "did", "do", "does",
    "have", "has", "had", "in", "on", "at", "of", "to", "for", "or", "and", "any", "anything", "something", "some",
    "this", "that", "these", "those", "with", "from", "since", "about", "last", "few", "start", "started", "yes",
    "no", "i", "my", "me", "we", "us", "he", "she", "they", "them", "his", "her", "their", "there", "here", "what",
    "when", "how", "bad", "if", "not", "new"})


def _strip(regex: re.Pattern, text: str) -> str:
    return regex.sub(" ", text)


def _residue(text: str) -> str:
    """`text` without punctuation and filler words, lower case, single-spaced."""
    cleaned = _strip(_FILLER_RE, text.lower())
    return " ".join(_WORD_RE.findall(cleaned))


def _is_no_answer(text: str) -> bool:
    if not _WORD_RE.search(text):
        return True  # empty, silence, "...", "?"
    residue = _residue(text)
    return not " ".join(_WORD_RE.findall(_strip(_NO_ANSWER_RE, residue)))


def _is_hedge_only(text: str) -> bool:
    residue = _residue(text)
    if not _HEDGE_RE.search(residue):
        return False
    rest = _strip(_HEDGE_RE, residue)
    rest = _strip(_NO_ANSWER_RE, rest)
    return not _WORD_RE.findall(rest)


def polarity(text: str) -> str | None:
    """"yes" / "no" when the answer starts with a clear yes or no (after filler) or a very short answer holds
    only one of them; None when it holds neither, both ("yes and no") or a hedge."""
    residue = _residue(text)
    if not residue or _HEDGE_RE.search(residue):
        return None
    yes_m, no_m = _YES_RE.match(residue), _NO_RE.match(residue)
    if yes_m and no_m:  # "i did" vs "i didn't": the longer match is the real one
        return "yes" if len(yes_m.group()) > len(no_m.group()) else "no"
    if yes_m or no_m:
        first = "yes" if yes_m else "no"
        rest = residue[(yes_m or no_m).end():]
        other = _NO_RE if first == "yes" else _YES_RE
        # "yes, no wait" / "no... yes": contradictory start
        if other.match(rest.strip()):
            return None
        return first
    if len(residue.split()) <= 6:
        has_yes, has_no = bool(_YES_RE.search(residue)), bool(_NO_RE.search(residue))
        if has_yes != has_no:
            return "yes" if has_yes else "no"
    return None


# --- Question shape -----------------------------------------------------------------------------------------------
_YES_NO_START_RE = re.compile(r"^\s*(?:did|do|does|have|has|had|is|are|was|were|can|could|will|would|any|anything)"
                              r"\b", re.IGNORECASE)
_YES_OR_NO_RE = re.compile(r"\byes\s*(?:,|or)\s*no\b", re.IGNORECASE)


def is_yes_no(ask_text: str) -> bool:
    """A yes / no question: says "yes or no", or starts like one and offers no list of choices."""
    if _YES_OR_NO_RE.search(ask_text):
        return True
    return bool(_YES_NO_START_RE.match(ask_text)) and not choices(ask_text)


_LEAD_RE = re.compile(r"^\s*(?:is|are|was|were|did|does|do|has|have)\s+(?:it|they|you|this|that|he|she)\s+"
                      r"(?:(?:a|an|the)\s+)?(?:start|started|been|feel|felt)?\s*", re.IGNORECASE)


def choices(ask_text: str) -> list[tuple[str, ...]]:
    """The listed choices of a choice question ("Is it a rash, a nail problem, or nothing new?" -> rash /
    nail problem / nothing new), each as its content words; [] when it lists fewer than two."""
    if _YES_OR_NO_RE.search(ask_text) or not re.search(r"\bor\b", ask_text, re.IGNORECASE):
        return []
    body = ask_text.strip().rstrip("?.! ")
    body = _LEAD_RE.sub("", body)
    parts = [p for p in re.split(r",\s*(?:or\s+)?|\s+or\s+", body, flags=re.IGNORECASE) if p.strip()]
    out = []
    for part in parts:
        words = tuple(w for w in _WORD_RE.findall(part.lower()) if w not in _STOPWORDS or w in ("today",))
        if words:
            out.append(words)
    return out if len(out) >= 2 else []


def _choice_match(ask_text: str, text: str) -> bool:
    """(Re-asks only, short answers.) Exactly one listed choice is named (any of its content words, whole word)."""
    options = choices(ask_text)
    if not options:
        return False
    words = set(_WORD_RE.findall(text.lower()))
    hits = [opt for opt in options if any(w in words or (w.endswith("s") and w[:-1] in words) for w in opt)]
    return len(hits) == 1


# --- Topic rules --------------------------------------------------------------------------------------------------
def _mentions_symptom(text: str) -> bool:
    """A symptom word from the term list (schema words or curated cues, negated or not) or a general health word."""
    for code in extract._cue_regexes():
        if extract._grounding(code, text) != "ungrounded":
            return True
    return bool(_HEALTH_RE.search(text))


def _answers(purpose: str, ask: int, ask_text: str, text: str) -> str | None:
    """COMPLETE / PARTIAL when a rule can tell this (short) text answers the ask; None when the rules cannot."""
    yes_no = is_yes_no(ask_text)
    pol = polarity(text)
    if purpose == "severity" and severity_in_text(text):
        return COMPLETE
    if purpose == "onset" and onset_in_text(text):
        return COMPLETE
    if ask >= 1 and _word_count(text) <= 10 and _choice_match(ask_text, text) and not _is_hedge_only(text):
        return COMPLETE
    if purpose == "adherence" and (pol or _ADHERENCE_RE.search(text)):
        return COMPLETE
    if purpose == "symptom_screen":
        if pol == "no" or _mentions_symptom(text):
            return COMPLETE
        if pol == "yes" and _word_count(_residue(text)) <= 3:
            return COMPLETE if _YES_OR_NO_RE.search(ask_text) else PARTIAL  # "yes" but what?
    if purpose == "exposure":
        if pol == "no":
            return COMPLETE
        if pol == "yes" and _word_count(_residue(text)) <= 3:
            return COMPLETE if _YES_OR_NO_RE.search(ask_text) else PARTIAL  # "yes" but what?
    if purpose == "wellbeing" and (_FEELING_RE.search(text) or _mentions_symptom(text)):
        return COMPLETE
    if yes_no and pol:
        return COMPLETE
    if _is_hedge_only(text):
        return PARTIAL
    return None


def _on_topic(purpose: str, ask: int, ask_text: str, sentence: str) -> bool:
    """A rule says this one sentence is about the question (used to find the answer inside a long reply)."""
    if _answers(purpose, ask, ask_text, sentence) == COMPLETE:
        return True
    if purpose == "severity":
        return _mentions_symptom(sentence) and bool(re.search(
            r"(?<![\w'])(?:bad|worse|better|hurts?|unbearable|can'?t|cannot|stop\w*|bearable|manageable|lot)"
            r"(?![\w'])", sentence, re.IGNORECASE))
    if purpose == "exposure":
        return bool(_EXPOSURE_RE.search(sentence)) and bool(re.search(r"(?<![\w'])(?:new|started|switched|changed|"
                                                                    r"began|tried|trying)(?![\w'])", sentence,
                                                                    re.IGNORECASE))
    return False


def _is_filler_sentence(sentence: str) -> bool:
    return not _residue(sentence) or _is_no_answer(sentence)


def _is_long(text: str, sentences: list[str]) -> bool:
    words = _word_count(text)
    return words > LONG_WORDS or (len(sentences) >= 4 and words > 30)


def _rules(purpose, ask, ask_text, text, sentences) -> tuple[str, str] | None:
    if _is_no_answer(text):
        return NO_ANSWER, ""
    if _is_long(text, sentences):
        content = [s for s in sentences if not _is_filler_sentence(s)]
        on = [s for s in content if _on_topic(purpose, ask, ask_text, s)]
        if not on:
            return None
        off_words = sum(_word_count(s) for s in content if s not in on)
        if off_words >= OFF_TOPIC_SHARE * _word_count(text):
            return RAMBLING, _join(on)
        return COMPLETE, _join(content)
    decided = _answers(purpose, ask, ask_text, text)
    if decided is not None:
        return decided, _join([s for s in sentences if not _is_filler_sentence(s)]) or text.strip()
    return None


def _fallback(purpose, ask, ask_text, text, sentences) -> tuple[str, str]:
    """No model: re-ask either way. On-topic sentences -> partial with them; else short -> partial (kept for the
    person reviewing); long with nothing on topic -> off_topic."""
    content = [s for s in sentences if not _is_filler_sentence(s)]
    on = [s for s in content if _on_topic(purpose, ask, ask_text, s)
          or (purpose in ("symptom_screen", "severity", "wellbeing") and _mentions_symptom(s))]
    if on:
        return PARTIAL, _join(on)
    if not _is_long(text, sentences):
        return PARTIAL, _join(content) or text.strip()
    return OFF_TOPIC, ""


# --- Model --------------------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def output_schema() -> dict:
    """JSON schema passed to Ollama's `format`: {"rating": <answer_rating>, "relevant_sentences": [int]}."""
    return {
        "type": "object",
        "properties": {
            "rating": {"type": "string", "enum": list(RATINGS)},
            "relevant_sentences": {"type": "array", "items": {"type": "integer", "minimum": 0},
                                   "maxItems": MAX_SENTENCES},
        },
        "required": ["rating", "relevant_sentences"],
        "additionalProperties": False,
    }


_PURPOSES = {
    "wellbeing": "how the patient has been feeling in general",
    "symptom_screen": "whether the patient has a new symptom, and which one",
    "severity": "how bad the symptom is (mild, moderate, severe, or how much it stops normal life)",
    "onset": "when the symptom started",
    "adherence": "whether the patient took their medicine",
    "exposure": "whether the patient started using, eating or doing anything new, and what",
}

_SYSTEM_PROMPT = """You check whether a patient's spoken answer answers the question they were asked in a health \
check-in. Reply with JSON only: {"rating": ..., "relevant_sentences": [...]}.

The answer is given as numbered sentences. Personal details were replaced by placeholders such as [NAME]; ignore \
them. The speaker may be the patient or a parent or carer answering for them.

rating:
- "complete": the answer gives what the question asks for.
- "partial": the answer is about the question but does not give what it asks for (a symptom but not how bad when \
the question asks how bad; "sort of"; "yes" when the question also asks what).
- "off_topic": the answer talks about something else and does not answer the question.
- "rambling": a long answer that talks mostly about other things but does contain the answer somewhere.
- "no_answer": no answer at all ("I don't know", "what?", silence).

relevant_sentences: the numbers of the sentences that answer the question (only those). Use [] for off_topic \
and no_answer."""

# Few-shot examples (Scoping Doc 17.2). Written for the prompt; never reuse them as evaluation cases.
_EXAMPLES = (
    ("severity", "How bad is it?",
     ["My arm is itchy.", "It's red too."], PARTIAL, [0, 1]),
    ("onset", "When did it start?",
     ["I had toast for breakfast and then watched the news."], OFF_TOPIC, []),
    ("symptom_screen", "Have you noticed anything new on your skin or nails?",
     ["Well my neighbour's been doing building work all week and the noise is driving me mad.",
      "The council said it would finish by Friday but they always say that.",
      "Oh and my fingertips have gone a bit cracked.",
      "Anyway the builders park right across my drive."], RAMBLING, [2]),
    ("exposure", "Anything new you started using, eating or doing?",
     ["I switched to a new washing powder last week."], COMPLETE, [0]),
    ("wellbeing", "How have you been feeling since yesterday?",
     ["The weather has been lovely."], OFF_TOPIC, []),
    ("adherence", "Did you take your medicine today?",
     ["My cousin rang from abroad last night and we talked for two hours.",
      "She is moving house next month and the new place has a big garden.",
      "We talked about her children and their school as well."], OFF_TOPIC, []),
    ("onset", "When did it start?", ["Sorry, what?"], NO_ANSWER, []),
)


def _numbered(sentences: list[str]) -> str:
    return "\n".join(f"{i}: {s}" for i, s in enumerate(sentences[:MAX_SENTENCES]))


def _user(purpose: str, ask_text: str, sentences: list[str]) -> str:
    return (f"Question: {ask_text}\nThe question is about: {_PURPOSES.get(purpose, 'the question above')}\n"
            f"Answer sentences:\n{_numbered(sentences)}")


def _messages(purpose: str, ask_text: str, sentences: list[str]) -> list[dict]:
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for ex_purpose, ex_ask, ex_sentences, ex_rating, ex_indices in _EXAMPLES:
        messages.append({"role": "user", "content": _user(ex_purpose, ex_ask, ex_sentences)})
        messages.append({"role": "assistant",
                         "content": json.dumps({"rating": ex_rating, "relevant_sentences": ex_indices})})
    messages.append({"role": "user", "content": _user(purpose, ask_text, sentences)})
    return messages


def _parse(response: Any) -> dict | None:
    """The model's JSON object, or None when it is unusable (never keeps the content anywhere)."""
    try:
        content = response["message"]["content"]
    except (KeyError, TypeError, IndexError, AttributeError):
        return None
    if not isinstance(content, str):
        return None
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("rating") not in RATINGS:
        return None
    return data


def _indices(value: Any, count: int) -> list[int]:
    """Valid, unique sentence indices in input order; anything else (strings, bools, out of range) dropped."""
    if not isinstance(value, list):
        return []
    limit = min(count, MAX_SENTENCES)
    return sorted({i for i in value if isinstance(i, int) and not isinstance(i, bool) and 0 <= i < limit})


def _validate(data: dict, purpose, ask, ask_text, text, sentences) -> tuple[str, str]:
    """Rules over the model: quote only input sentences and keep the length rules."""
    rating = data["rating"]
    if rating == NO_ANSWER:
        # The rules already decided every no-answer case they recognise; real words the model calls "no answer"
        # do not answer the question, so they are off topic (a 3B model mixes the two up).
        return OFF_TOPIC, ""
    if rating == OFF_TOPIC:
        return rating, ""
    picked = [sentences[i] for i in _indices(data.get("relevant_sentences"), len(sentences))]
    picked = [s for s in picked if not _is_filler_sentence(s)]
    content = [s for s in sentences if not _is_filler_sentence(s)]
    long = _is_long(text, sentences)
    if rating == RAMBLING:
        if not picked:
            return OFF_TOPIC, ""  # rambling with no answer in it is off topic
        if _word_count(text) <= SHORT_WORDS:
            return COMPLETE, _join(picked)  # a short answer cannot ramble
        return RAMBLING, _join(picked)
    # complete / partial
    if not picked:
        picked = content
    if rating == COMPLETE and long and len(picked) < len(content):
        off_words = sum(_word_count(s) for s in content if s not in picked)
        if off_words >= OFF_TOPIC_SHARE * _word_count(text):
            return RAMBLING, _join(picked)
    return rating, _join(picked) or text.strip()
