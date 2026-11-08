"""Constrained extraction into coded fields (PV-02, SE-01, SE-02 groundwork, VC-10). Local model only.

`extract_symptoms(filtered_text)` asks the local Ollama model (default `llama3.2:3b`, temperature 0) for the
symptoms in an already filtered answer (see `filter.redact`). The output is forced into a JSON schema whose
term codes, severities and onsets are the enums in schema/, plus a per-item `match` ("clear" | "unsure"), and is
validated again here regardless of the model (rules override the model, Scoping Doc 17.1):
- unknown code -> SE_OTHER_REVIEW (D-015);
- grounding: a specific term is kept only when the text has a cue for it (its label_term, everyday_words, or the
  curated cues below); no cue -> SE_OTHER_REVIEW ("my chest feels tight" is never SE_COUGH). When every cue for it
  is negated or said to have stopped ("no rash", "the diarrhea has stopped"), the item is dropped;
- `match: "unsure"` -> SE_OTHER_REVIEW (a person reviews it; no guessing), unless the text uses the term's own
  schema words (label_term, everyday_words): that is a dictionary match, not a guess;
- severity / onset must agree with the plain words in the text (`severity_in_text`, `onset_in_text` use the same
  rules): a level or onset the text does not support -> None / "unknown" (re-asked later, VC-10);
- duplicates dropped (first wins), at most 10 items.

`severity_in_text(text)` and `onset_in_text(text)` are rule-based (no model call), for answers to the survey's
severity and onset questions, which usually name no symptom. Both return None when the text says nothing clear.

`known_side_effect` is not decided here: it is a deterministic lookup of the term code in
`term_cache.known_for_program` (D-007), done by the caller.

Privacy: Ollama must be on a loopback address (PATIENT_OLLAMA_HOST, default http://127.0.0.1:11434), proxies and
redirects are disabled, and nothing here logs or prints text or model output. Error messages never contain them.
This is the only module that imports `ollama`.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sentinel_contract import SCHEMA_DIR, enums

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
OTHER_REVIEW = "SE_OTHER_REVIEW"
NOT_STATED = "not_stated"
MATCH_CLEAR, MATCH_UNSURE = "clear", "unsure"
MAX_SYMPTOMS = 10
TIMEOUT_SECONDS = 120  # the first call loads the model into memory


@dataclass(frozen=True)
class ExtractedSymptom:
    term_code: str           # one of enums()["term_code"]; anything unmapped -> "SE_OTHER_REVIEW" (D-015)
    severity: str | None     # "mild" | "moderate" | "severe", or None when not stated (re-asked later, VC-10)
    onset: str               # one of enums()["onset"]; "unknown" when not stated


class ExtractionError(RuntimeError):
    """The model output was unusable. The message never contains the text or the model output."""


class ExtractionUnavailable(ExtractionError):
    """Ollama is unreachable or the model is missing. The message names the host and model only."""


def extract_symptoms(filtered_text: str, *, client: Any = None) -> list[ExtractedSymptom]:
    """Code the symptoms in `filtered_text` (already passed through `filter.redact`).

    `client`: anything with `.chat(model=..., messages=..., format=..., options=...)` returning a mapping where
    `["message"]["content"]` is the JSON string; defaults to an `ollama.Client` on the loopback host.
    Raises ValueError for a non-loopback PATIENT_OLLAMA_HOST, ExtractionUnavailable when the model cannot be
    reached, ExtractionError when its output is unusable.
    """
    host, model = ollama_host(), ollama_model()
    if not filtered_text or not filtered_text.strip():
        return []
    if client is None:
        client = _default_client(host)

    failure: ExtractionError | None = None
    try:
        response = client.chat(model=model, messages=_messages(filtered_text), format=output_schema(),
                               options={"temperature": 0})
    except Exception as exc:  # noqa: BLE001 - mapped below; raised outside this block so no context is chained
        failure = _client_failure(exc, host, model)
    if failure is not None:
        raise failure
    return _validate(_parse(response), filtered_text)


# --- Settings ---------------------------------------------------------------------------------------------------
def ollama_host() -> str:
    """PATIENT_OLLAMA_HOST (default http://127.0.0.1:11434). Raises ValueError unless it is a loopback address."""
    host = (os.environ.get("PATIENT_OLLAMA_HOST") or DEFAULT_HOST).strip()
    if _hostname(host) not in LOOPBACK_HOSTS:
        raise ValueError(f"PATIENT_OLLAMA_HOST must be a loopback address (127.0.0.1, ::1 or localhost): {host!r}")
    return host


def ollama_model() -> str:
    return (os.environ.get("PATIENT_OLLAMA_MODEL") or DEFAULT_MODEL).strip()


def _hostname(host: str) -> str | None:
    """Host name of an Ollama host string ("127.0.0.1:11434", "http://localhost", "[::1]:11434"), or None when
    it cannot be parsed safely (user info, query, fragment, unknown scheme, bad port)."""
    scheme, sep, rest = host.partition("://")
    if not sep:
        scheme, rest = "http", host
    if scheme.lower() not in ("http", "https"):
        return None
    netloc = rest.split("/", 1)[0]
    if not netloc or any(c in netloc for c in "@?#\\%") or any(c.isspace() for c in netloc):
        return None
    if netloc == "::1":
        return "::1"
    if netloc.startswith("["):
        end = netloc.find("]")
        name, port = (netloc[1:end], netloc[end + 1:]) if end > 0 else ("", "")
        if port and not (port.startswith(":") and port[1:].isdigit()):
            return None
        return name.lower() or None
    name, _, port = netloc.partition(":")
    if port and not port.isdigit():
        return None
    return name.lower() or None


@lru_cache(maxsize=4)
def _default_client(host: str):
    import ollama

    # trust_env=False: ignore HTTP(S)_PROXY so the request cannot be routed off the device; no redirects either.
    return ollama.Client(host=host, timeout=TIMEOUT_SECONDS, trust_env=False, follow_redirects=False)


# --- Contract-derived vocabularies ------------------------------------------------------------------------------
def term_codes() -> tuple[str, ...]:
    return tuple(enums()["term_code"])


def _severities() -> tuple[str, ...]:
    return tuple(enums()["severity"])


def _onsets() -> tuple[str, ...]:
    return tuple(enums()["onset"])


@lru_cache(maxsize=1)
def _terms() -> dict[str, dict]:
    """schema/terms.json rows by term code (label_term, everyday_words), for the prompt."""
    rows = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
    return {row["term_code"]: row for row in rows}


@lru_cache(maxsize=1)
def output_schema() -> dict:
    """JSON schema passed to Ollama's `format`: {"symptoms": [{term_code, match, severity, onset}]}."""
    return {
        "type": "object",
        "properties": {
            "symptoms": {
                "type": "array",
                "maxItems": MAX_SYMPTOMS,
                "items": {
                    "type": "object",
                    "properties": {
                        "term_code": {"type": "string", "enum": list(term_codes())},
                        "match": {"type": "string", "enum": [MATCH_CLEAR, MATCH_UNSURE]},
                        "severity": {"type": "string", "enum": [*_severities(), NOT_STATED]},
                        "onset": {"type": "string", "enum": list(_onsets())},
                    },
                    "required": ["term_code", "match", "severity", "onset"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["symptoms"],
        "additionalProperties": False,
    }


# --- Prompt -----------------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _term_lines() -> str:
    lines = []
    for code in term_codes():
        if code == OTHER_REVIEW:
            continue
        row = _terms().get(code)
        if row is None:
            lines.append(f"- {code}")
            continue
        words = ", ".join(row["everyday_words"])
        lines.append(f"- {code}: {row['label_term']}" + (f". People say: {words}" if words else ""))
    lines.append(f"- {OTHER_REVIEW}: any other symptom or health problem that is not in this list "
                 "(for example headache, nausea, fever, dizziness, pain)")
    return "\n".join(lines)


_SYSTEM_PROMPT = """You code a patient's check-in answer into symptoms for a drug-safety study. Reply with JSON only.

Personal details in the answer were replaced by placeholders such as [NAME] or [PLACE]; ignore them.
The speaker is the patient or someone answering for the patient (a parent or a caregiver). Code the patient's \
symptoms either way.

Term codes (use only these):
{terms}

Rules:
1. Include a symptom only if the answer says the patient has it now. Leave out symptoms the answer says the \
patient does not have ("no rash", "not tired", "the cough has gone") and symptoms that are only asked about or \
feared.
2. One item per symptom. Never add a symptom that is not mentioned. Anything not in the list is \
{other}. If no symptom is reported, return {{"symptoms": []}}.
3. severity: "mild", "moderate" or "severe" only when the answer says how bad that symptom is (a little, \
slight -> mild; quite bad, moderate -> moderate; very bad, terrible, unbearable, cannot do normal things -> \
severe). If the answer does not say how bad it is, use "{not_stated}"; never guess.
4. onset: when the symptom started. "today"; "1_3_days" (yesterday, two or three days ago); "4_7_days" \
(four to seven days ago, about a week, last week); "over_7_days" (more than a week ago, weeks or months); \
"unknown" when the answer does not say when it started; never guess.
5. match: "{clear}" when the answer plainly names that symptom (the term, its everyday words above, or an obvious \
synonym). "{unsure}" when the answer only describes something that might be that symptom (another body part, \
another kind of feeling, a vague complaint). Unsure items are checked by a person, so never force a symptom into \
a term.
Today is {weekday}."""


def _example(code: str, severity: str = NOT_STATED, onset: str = "unknown", match: str = MATCH_CLEAR) -> dict:
    return {"term_code": code, "match": match, "severity": severity, "onset": onset}


# Few-shot examples (Scoping Doc 17.2). Written for the prompt; never reuse them as evaluation cases.
_EXAMPLES = (
    ("I've had a really bad rash on my arms since yesterday. No diarrhea though.",
     [_example("SE_RASH", "severe", "1_3_days")]),
    ("[NAME] here, I'm calling for my dad. He's been a bit tired for about a week, his ankles are puffy and he "
     "keeps getting headaches.",
     [_example("SE_FATIGUE", "mild", "4_7_days"), _example("SE_EDEMA"), _example(OTHER_REVIEW)]),
    ("She's off her food and her skin is flaky. She doesn't have a cough.",
     [_example("SE_DECREASED_APPETITE"), _example("SE_DRY_SKIN")]),
    ("My eyelids look a bit heavy and my knee hurts.",
     [_example("SE_EDEMA", "mild", match=MATCH_UNSURE), _example(OTHER_REVIEW)]),
    ("Feeling fine today, nothing new to report.", []),
)


def _messages(filtered_text: str) -> list[dict]:
    system = _SYSTEM_PROMPT.format(terms=_term_lines(), other=OTHER_REVIEW, not_stated=NOT_STATED,
                                   clear=MATCH_CLEAR, unsure=MATCH_UNSURE,
                                   weekday=datetime.date.today().strftime("%A"))
    messages = [{"role": "system", "content": system}]
    for text, symptoms in _EXAMPLES:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": json.dumps({"symptoms": symptoms})})
    messages.append({"role": "user", "content": filtered_text})
    return messages


# --- Errors -----------------------------------------------------------------------------------------------------
_TRANSPORT_ERRORS = {"TransportError", "TimeoutException", "NetworkError", "ConnectError", "ProxyError"}


def _client_failure(exc: Exception, host: str, model: str) -> ExtractionError:
    """Map a client exception to our errors without carrying its message (it could echo content)."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)) or \
            _TRANSPORT_ERRORS & {cls.__name__ for cls in type(exc).__mro__}:
        return ExtractionUnavailable(f"Ollama is not reachable at {host} (model {model})")
    status = getattr(exc, "status_code", None)
    if status == 404:
        return ExtractionUnavailable(f"model {model} is not available at {host}")
    if isinstance(status, int):
        return ExtractionError(f"local model call failed with HTTP {status} (model {model})")
    return ExtractionError(f"local model call failed: {type(exc).__name__} (model {model})")


def _parse(response: Any) -> dict:
    try:
        content = response["message"]["content"]
    except (KeyError, TypeError, IndexError, AttributeError):
        content = None
    if not isinstance(content, str):
        raise ExtractionError("model response has no message content")
    try:
        data = json.loads(content)
    except ValueError:
        data = None  # raised below, outside the except block, so the decode error (it holds the text) is dropped
    if not isinstance(data, dict) or not isinstance(data.get("symptoms"), list):
        raise ExtractionError("model output is not the expected JSON object")
    return data


# --- Post-validation: rules override the model (Scoping Doc 17.1) -----------------------------------------------
def _validate(data: dict, filtered_text: str = "", today: datetime.date | None = None) -> list[ExtractedSymptom]:
    text = _normalise(filtered_text)
    codes = set(term_codes())
    # A severity or onset the text does not support is a guess (a guessed "severe" would raise an alert), so it is
    # dropped and re-asked (VC-10). With no recognisable time phrase but some time words ("recently"), the model's
    # onset is kept as before.
    severity_ok = _severity_levels(text)
    onset_ok = _onset_buckets(text, today or datetime.date.today()) or \
        (set(_onsets()) if _TIME_CUE_RE.search(text) else set())
    out: list[ExtractedSymptom] = []
    seen: set[str] = set()
    for item in data["symptoms"]:
        if not isinstance(item, dict):
            continue
        code = _clean(item.get("term_code"), str.upper)
        code = code if code in codes else OTHER_REVIEW
        if code != OTHER_REVIEW:
            grounding = _grounding(code, text)
            if grounding == _DENIED:
                continue
            if grounding == _UNGROUNDED or \
                    (grounding == _WEAK and _clean(item.get("match"), str.lower) == MATCH_UNSURE):
                code = OTHER_REVIEW
        if code in seen:
            continue
        seen.add(code)
        out.append(ExtractedSymptom(
            term_code=code,
            severity=_agree(_clean(item.get("severity"), str.lower), severity_ok, set(_severities()), None),
            onset=_agree(_clean(item.get("onset"), str.lower), onset_ok, set(_onsets()), "unknown")))
        if len(out) == MAX_SYMPTOMS:
            break
    return out


def _agree(value: str | None, supported: set[str] | frozenset[str], valid: set[str], unset: str | None):
    """The model's value when the text supports it. When the text names exactly one value and the model gave a
    different one, the text wins (the model's date arithmetic and level words are less reliable). Else `unset`."""
    if value in supported:
        return value
    if len(supported) == 1 and value in valid and value != unset:
        return next(iter(supported))
    return unset


def _clean(value: Any, case) -> str | None:
    return case(value.strip()) if isinstance(value, str) else None


def _normalise(text: str) -> str:
    """Curly apostrophes -> straight (same length, so match offsets stay valid)."""
    return (text or "").replace("\u2019", "'").replace("\u2018", "'")


def _words_re(fragments) -> re.Pattern | None:
    """One case-insensitive regex for whole-word fragments, longest first."""
    if not fragments:
        return None
    alternatives = "|".join(sorted(fragments, key=len, reverse=True))
    return re.compile(rf"(?<![\w'])(?:{alternatives})(?![\w'])", re.IGNORECASE)


# --- Grounding guard ----------------------------------------------------------------------------------------------
# A specific term code is kept only when the filtered text contains a cue for it: its label_term or everyday_words
# (schema/terms.json) or one of the curated cues below (regex fragments, whole words, case-insensitive). Cues are
# deliberately broad: the guard only catches codes the text gives no reason for (the model codes "my chest feels
# tight" as SE_COUGH because "chesty" is a cough word, but "chest" is not "chesty"); it never adds a code.
_CUES: dict[str, tuple[str, ...]] = {
    "SE_RASH": (r"rash\w*", r"spots?", r"spotty", r"itch\w*", r"bumps?", r"bumpy", r"pimples?", r"zits?", r"acne",
                r"hives", r"welts?", r"blotch\w*", r"pustules?", r"eczema", r"redness", r"broken?\s+out",
                r"breakouts?", r"red\s+(?:patch\w*|marks?|areas?|skin)", r"skin\s+(?:[\w']+\s+){0,2}red"),
    "SE_DRY_SKIN": (r"dry", r"dryness", r"flak\w*", r"peel\w*", r"scaly", r"scaling", r"chapped", r"crack\w*",
                    r"rough", r"split\w*\s+skin", r"skin\s+(?:[\w']+\s+){0,2}(?:tight|split\w*)"),
    "SE_PARONYCHIA": (r"(?:finger|toe)?nails?", r"nail\s*beds?", r"cuticles?", r"finger\s*tips?", r"paronychia",
                      r"ingrown", r"whitlows?"),
    "SE_DIARRHEA": (r"diarrh\w*", r"loose\w*", r"the\s+runs", r"the\s+trots", r"stools?", r"bowels?",
                    r"bowel\s+movements?", r"poos?", r"poop\w*", r"pooing", r"toilet", r"bathroom", r"loo",
                    r"nappies", r"nappy", r"diapers?",
                    r"runny\s+(?:tummy|stomach|poos?|poop|stools?)",
                    r"(?:tummy|stomach|bowels?)\s+(?:[\w']+\s+){0,2}running",
                    r"watery\s+(?:stools?|poos?|poop|bowel\w*|nappies|diapers?)"),
    "SE_STOMATITIS": (r"ulcers?", r"canker", r"sores", r"stomatitis", r"mucositis", r"gums?", r"tongue", r"lips?",
                      r"mouth\s+(?:[\w']+\s+){0,3}?(?:sore\w*|ulcer\w*|blister\w*|hurt\w*|pain\w*|burn\w*|raw|red|"
                      r"cuts?|bleed\w*|tender|inflam\w*|swollen|sting\w*)",
                      r"(?:sore|ulcer\w*|blister\w*|painful|burn\w*|raw|cuts?|bleed\w*|tender|inflam\w*|swollen)\s+"
                      r"(?:[\w']+\s+){0,3}?mouth",
                      r"(?:hurts?|painful|sore)\s+to\s+(?:eat|chew)"),
    "SE_FATIGUE": (r"tired\w*", r"fatigu\w*", r"exhaust\w*", r"worn\s+out", r"wiped\s+out", r"run\s+down",
                   r"drained", r"weary", r"letharg\w*", r"sluggish", r"knackered", r"shattered", r"sleepy",
                   r"drowsy", r"listless", r"floppy", r"weak\w*", r"no\s+get\s+up\s+and\s+go"),
    "SE_INFUSION_REACTION": (r"infus\w*", r"drip", r"iv", r"cannula", r"reactions?", r"transfusion", r"chemo\w*",
                             r"treatment", r"session"),
    "SE_COUGH": (r"cough\w*", r"chesty", r"phlegm", r"mucus", r"sputum", r"hacking", r"bark\w*",
                 r"clearing\s+(?:[\w']+\s+)?throat"),
    "SE_EDEMA": (r"swell\w*", r"swollen", r"puffy", r"puffiness", r"puffed\s+up", r"o?edema\w*", r"fluid",
                 r"water\s+(?:retention|weight)", r"retain\w*\s+(?:water|fluid)", r"pitting",
                 r"(?:shoes|socks|rings?)\s+(?:[\w']+\s+){0,2}tight", r"tight\s+(?:shoes|socks|rings?)"),
}
# Cues that ground a term but whose negation does not mean the symptom is absent ("no energy", "not hungry",
# "can't catch my breath"). Terms in _ABSENCE_TERMS treat their schema words this way too.
_NEUTRAL_CUES: dict[str, tuple[str, ...]] = {
    "SE_FATIGUE": (r"energy",),
    "SE_DECREASED_APPETITE": (r"appetite", r"hung(?:ry|er)", r"eat\w*", r"ate", r"food", r"meals?", r"feed\w*",
                              r"fed", r"bottles?", r"snack\w*", r"nibbl\w*", r"picking\s+at"),
    "SE_DYSPNEA": (r"breath\w*", r"winded", r"puff(?:ed)?", r"gasp\w*", r"panting", r"wheez\w*", r"suffocat\w*",
                   r"dyspn\w*", r"air\s+hunger", r"smother\w*",
                   r"(?:[\w]+n't|cannot|can\s+not)\s+(?:get\s+)?(?:enough\s+)?air"),
}
_ABSENCE_TERMS = frozenset({"SE_DECREASED_APPETITE", "SE_DYSPNEA"})
# Phrases that look like a cue for the term but are something else ("dry mouth" is not dry skin).
_NOT_CUES: dict[str, tuple[str, ...]] = {
    "SE_DRY_SKIN": (r"dry\s+(?:mouth|eyes?|throat|nose|cough|heav\w*)",
                    r"(?:mouth|eyes?|throat|nose|cough)\s+(?:[\w']+\s+){0,2}?dry"),
    "SE_DIARRHEA": (r"runny\s+nose", r"(?:nappy|diaper)\s+rash"),
    "SE_RASH": (r"(?:see\w*|saw)\s+spots", r"spots\s+(?:in|before)\s+(?:[\w']+\s+)?(?:eyes?|vision)",
                r"itch\w*\s+(?:eyes?|throat|ears?)", r"(?:eyes?|throat|ears?)\s+(?:[\w']+\s+){0,2}?itch\w*"),
    "SE_STOMATITIS": (r"stomach\s+ulcers?",),
    "SE_FATIGUE": (r"tired\s+of", r"sick\s+and\s+tired"),
    "SE_DYSPNEA": (r"bad\s+breath", r"breath\s+smells?"),
    "SE_EDEMA": (r"swollen\s+(?:glands?|lymph\w*|tonsils?|gums?)",
                 r"(?:glands?|lymph\s+nodes?|tonsils?|gums?)\s+(?:[\w']+\s+){0,2}?swollen"),
}
# STRONG: the term's own schema words (label_term, everyday_words) are in the text, so even a model "unsure" is not
# a guess. WEAK: only a curated cue. UNGROUNDED: no cue (-> SE_OTHER_REVIEW). DENIED: every cue is negated or has
# stopped (-> dropped).
_STRONG, _WEAK, _UNGROUNDED, _DENIED = "strong", "weak", "ungrounded", "denied"


@lru_cache(maxsize=1)
def _cue_regexes() -> dict[str, tuple[re.Pattern | None, ...]]:
    """term code -> (cues a negation can deny, cues it cannot, not-cues, the term's schema words)."""
    out = {}
    for code in term_codes():
        if code == OTHER_REVIEW:
            continue
        row = _terms().get(code, {})
        schema_words = [r"\s+".join(re.escape(w) for w in _normalise(phrase).split())
                        for phrase in [row.get("label_term", ""), *row.get("everyday_words", [])] if phrase.strip()]
        present, neutral = list(_CUES.get(code, ())), list(_NEUTRAL_CUES.get(code, ()))
        (neutral if code in _ABSENCE_TERMS else present).extend(schema_words)
        if present or neutral:
            out[code] = (_words_re(present), _words_re(neutral), _words_re(_NOT_CUES.get(code, ())),
                         _words_re(schema_words))
    return out


def _grounding(code: str, text: str) -> str:
    cues = _cue_regexes().get(code)
    if cues is None:
        return _STRONG  # a code with no words to check against (not in schema/terms.json): nothing to judge
    present_re, neutral_re, not_re, schema_re = cues
    if not_re is not None:
        text = not_re.sub(lambda m: " " * len(m.group()), text)

    def live(m: re.Match) -> bool:
        return code in _ABSENCE_TERMS or not (_negated(text, m.start(), m.end()) or _stopped(text, m.end()))

    if schema_re is not None and any(live(m) for m in schema_re.finditer(text)):
        return _STRONG
    if neutral_re is not None and neutral_re.search(text):
        return _WEAK
    hits = list(present_re.finditer(text)) if present_re is not None else []
    if not hits:
        return _UNGROUNDED
    return _WEAK if any(live(m) for m in hits) else _DENIED


_WORD_RE = re.compile(r"[A-Za-z']+")
_CLAUSE_BREAK_RE = re.compile(r"[.,;:!?()\[\]]|\b(?:but|though|although|however|except|whereas|yet|while)\b",
                              re.IGNORECASE)
_NEGATORS = frozenset({"no", "not", "never", "without", "none", "nothing", "neither", "nor"})
# A word between the negator and the cue that keeps the symptom: "can't stop coughing", "never been so tired",
# "not as itchy".
_HEDGES = frozenset({"so", "this", "that", "as", "too", "very", "more", "less", "much", "stop", "stopped",
                     "stopping", "help", "quit", "only", "even"})
_STILL_RE = re.compile(r"\s+(?:as|so|that)\s+(?:much|bad|badly|often)\b", re.IGNORECASE)
_STOP_END = r"(?=\s*(?:$|[.,;!?]|now\b|completely\b|totally\b|for\s+good\b|but\b|and\b|thank\w*|again\b|since\b))"
_STOPPED_RE = re.compile(
    r"(?:[\s,]+(?:has|have|had|is|are|was|were|it|it's|its|they|they're|that|that's|which|but|and|now|finally|"
    r"completely|totally|fully|all|mostly|already|just|since|then|thankfully|luckily|seems|seemed|to|got|gotten|"
    r"been|basically|pretty|much)){0,5}[\s,]+"
    rf"(?:(?:stopped|cleared(?:\s+up)?|disappeared|resolved|healed(?:\s+up)?|gone){_STOP_END}|went\s+away|gone\s+away)",
    re.IGNORECASE)


def _negated(text: str, start: int, end: int) -> bool:
    """A negator in the 3 words before the cue, in the same clause ("no rash", "I don't have a rash")."""
    before = text[:start]
    breaks = list(_CLAUSE_BREAK_RE.finditer(before))
    words = [w.lower() for w in _WORD_RE.findall(before[breaks[-1].end():] if breaks else before)][-3:]
    for i, word in enumerate(words):
        if word in _NEGATORS or word.endswith("n't"):
            return not (set(words[i + 1:]) & _HEDGES or _STILL_RE.match(text, end))
    return False


def _stopped(text: str, end: int) -> bool:
    """The cue is followed by "has stopped", "went away", "is gone", ... ("the diarrhea has stopped")."""
    return _STOPPED_RE.match(text, end) is not None


# --- Severity and onset from plain words (no model) --------------------------------------------------------------
def severity_in_text(filtered_text: str) -> str | None:
    """The severity level ("mild" | "moderate" | "severe") when the text names exactly one in plain words ("a
    little", "quite bad", "really bad", "7 out of 10"); None when it names none, several, or only a negated one
    ("not severe"). Same rules as the severity check in `extract_symptoms`."""
    levels = _severity_levels(_normalise(filtered_text))
    return next(iter(levels)) if len(levels) == 1 else None


def onset_in_text(filtered_text: str, *, today: datetime.date | None = None) -> str | None:
    """The onset ("today" | "1_3_days" | "4_7_days" | "over_7_days") when every time phrase in the text points to
    the same one ("this morning", "since Monday", "about a week", "two weeks"); None when there is none or they
    disagree. `today` (default: the local date) is used for weekdays. Same rules as the onset check in
    `extract_symptoms`."""
    buckets = _onset_buckets(_normalise(filtered_text), today or datetime.date.today())
    return next(iter(buckets)) if len(buckets) == 1 else None


_LEVEL_WORD = (r"(?:mild\w*|moderate\w*|severe\w*|serious\w*|terribl\w*|awful\w*|horribl\w*|unbearabl\w*|"
               r"extreme\w*|excruciating|bad(?:ly)?|slight\w*|medium|intense\w*)")
_INTENSIFIER = r"(?:very|really|so|super|incredibly|awfully|seriously|truly)"
_SYMPTOM_ADJ = (r"(?:sore|itchy|painful|tired|exhausted|swollen|dry|uncomfortable|weak|achy|tender|raw|puffy|"
                r"breathless|sick|ill|unwell|poorly|rough|tight|loose|runny|flaky|cracked|red|heavy|nasty)")
_NUMBER_WORDS = {"zero": 0, "a": 1, "an": 1, "one": 1, "two": 2, "couple": 2, "three": 3, "few": 3, "four": 4,
                 "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                 "fourteen": 14}
# Alternatives are tried in this order at each position; a phrase that starts earlier always wins.
_SEVERITY_PARTS = (
    ("mild_neg", r"(?:not|\w+n't)\s+(?:(?:feel|feels|look|looks|seem|seems|be)\s+)?"
                 r"(?:(?:too|that|so|very|really|all|overly)\s+){0,2}bad(?:ly)?"),        # "not too bad"
    ("neg", rf"(?:not|never|\w+n't)\s+(?:[\w']+\s+){{0,2}}?{_LEVEL_WORD}|{_LEVEL_WORD}\s*\?\s*no"),  # "not severe"
    ("skip", r"quite\s+a\s+(?:bit|lot)|a\s+lot|a\s+(?:little\s+)?bit\s+(?:more|worse|better|less)|"
             r"a\s+little\s+(?:more|worse|better|less)"),
    ("scale", r"(?:\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:/|out\s+of)\s*(?:10|ten)"),
    ("severe", r"(?:(?:very|really|so|extremely|quite|pretty|absolutely)\s+)?(?:severe\w*|terribl\w*|awful\w*|"
               r"horribl\w*|unbearabl\w*|excruciating|extreme\w*|agony|agonising|agonizing|intense\w*|worst)"
               rf"|{_INTENSIFIER}(?:\s+{_INTENSIFIER})?\s+bad(?:ly)?"
               r"|(?:can't|cannot|can\s+not|couldn't|unable\s+to|not\s+able\s+to)\s+(?:do\s+(?:anything|"
               r"normal\s+things|my\s+(?:normal|usual|daily)\s+\w+)|get\s+out\s+of\s+bed|function)|bed-?ridden"),
    ("moderate", r"(?:(?:quite|fairly|pretty|very|really)\s+)?moderate\w*|medium|middling|"
                 r"in\s+(?:the\s+)?(?:middle|between)|(?:quite|fairly|pretty|rather|reasonably)\s+bad(?:ly)?"),
    ("mild", r"(?:(?:very|really|quite|pretty|fairly|just|only)\s+)?(?:mild\w*|slight\w*|minor)"
             r"|(?:(?:just|only)\s+)?a\s+(?:little|tiny|wee)(?:\s+bit)?|(?:(?:just|only)\s+)?a\s+bit"
             r"|barely\s+(?:noticeable|there)"),
    ("bad", r"bad(?:ly)?"),                                                                # moderate or severe
    ("intense", rf"{_INTENSIFIER}\s+{_SYMPTOM_ADJ}"),                                      # moderate or severe
)
_SEVERITY_RE = re.compile(
    r"(?<![\w'])(?:" + "|".join(f"(?P<{name}>{rx})" for name, rx in _SEVERITY_PARTS) + r")(?![\w'])",
    re.IGNORECASE)
_SEVERITY_SUPPORT = {"mild_neg": {"mild"}, "neg": set(), "skip": set(), "severe": {"severe"},
                     "moderate": {"moderate"}, "mild": {"mild"}, "bad": {"moderate", "severe"},
                     "intense": {"moderate", "severe"}}


def _severity_levels(text: str) -> frozenset[str]:
    """Every severity level the (normalised) text supports; negated level words support none."""
    levels: set[str] = set()
    for m in _SEVERITY_RE.finditer(text):
        if m.lastgroup == "scale":
            first = m.group().split("/")[0].split()[0].lower()
            score = int(first) if first.isdigit() else _NUMBER_WORDS.get(first, 0)
            levels.add("mild" if score <= 3 else "moderate" if score <= 6 else "severe")
        else:
            levels |= _SEVERITY_SUPPORT[m.lastgroup]
    return frozenset(levels)


_NUM = (r"(?:\d{1,3}|(?:a\s+)?couple(?:\s+of)?|(?:a\s+)?few|an?|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|fourteen)")
_UNIT_DAYS = {"hour": 1 / 24, "day": 1, "night": 1, "week": 7, "month": 30, "year": 365}
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_NOT_AGE = r"(?![\s-]*old)"  # "my 2 year old" is an age, not an onset
_ONSET_PARTS = (
    ("neg", r"(?:not|\w+n't)\s+(?:[\w']+\s+){0,2}?(?:today|yesterday|this\s+(?:morning|afternoon|evening|week)|"
            r"last\s+(?:night|week|month))|not\s+(?:that\s+|so\s+)?long\s+ago"),
    ("skip", r"(?:in|within|during|over)\s+the\s+(?:last|past)\s+week|(?:less\s+than|under)\s+(?:a|one)\s+week|"
             r"(?:earlier\s+)?this\s+week|(?:last\s+|the\s+|this\s+)?weekend|several\s+\w+"),
    ("days2", r"the\s+day\s+before\s+yesterday"),
    ("today", r"(?:earlier\s+)?today|this\s+(?:morning|afternoon|evening)|tonight|just\s+now|"
              r"since\s+I\s+(?:woke|got)\s+up"),
    ("days1", r"yesterday|last\s+night"),
    ("long", r"(?:much|way|a\s+lot|a\s+long\s+time|long)\s+earlier|long\s+(?:before|ago)|(?:for\s+)?ages(?:\s+ago)?|"
             r"a\s+long\s+time(?:\s+ago)?|(?:more\s+than|over)\s+(?:a|one)\s+(?:week|fortnight)|"
             r"(?:last|a)\s+month|(?:a\s+)?fortnight"),
    ("week", r"(?:last|this\s+past|the\s+past)\s+week|(?:a|one)\s+week(?:\s+ago)?"),
    ("weekday", r"(?:last\s+)?(?:" + "|".join(_WEEKDAYS) + ")"),
    ("count", rf"(?:more\s+than\s+)?{_NUM}(?:\s+(?:or|to)\s+{_NUM}|\s*-\s*{_NUM})?\s+"
              rf"(?:hours?|days?|nights?|weeks?|months?|years?){_NOT_AGE}"),
    ("plural", rf"(?:weeks|months|years){_NOT_AGE}"),
)
_ONSET_RE = re.compile(
    r"(?<![\w'])(?:" + "|".join(f"(?P<{name}>{rx})" for name, rx in _ONSET_PARTS) + r")(?![\w'])", re.IGNORECASE)
_COUNT_RE = re.compile(
    rf"(?P<more>more\s+than\s+)?(?P<a>{_NUM})(?:\s+(?:or|to)\s+(?P<b>{_NUM})|\s*-\s*(?P<c>{_NUM}))?\s+"
    r"(?P<unit>hour|day|night|week|month|year)s?", re.IGNORECASE)
_FIXED_DAYS = {"today": 0, "days1": 1, "days2": 2, "week": 7, "long": 8, "plural": 8}
# Plain time words without a recognisable phrase ("recently", "it started"): the model's onset is kept.
_TIME_CUE_RE = re.compile(
    r"(?i)\b(?:today|tonight|yesterday|ago|since|recently|lately|started|starting|began|begun|overnight|weekend|"
    r"fortnight|days?|weeks?|months?|years?|hours?|morning|afternoon|evening|night|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b")


def _onset_buckets(text: str, today: datetime.date) -> set[str]:
    """The onset of every time phrase in the (normalised) text; negated or vague phrases count for none."""
    buckets: set[str] = set()
    for m in _ONSET_RE.finditer(text):
        kind = m.lastgroup
        if kind in _FIXED_DAYS:
            days = [_FIXED_DAYS[kind]]
        elif kind == "weekday":
            words = m.group().lower().split()
            days = [(today.weekday() - _WEEKDAYS.index(words[-1])) % 7 or (7 if words[0] == "last" else 0)]
        elif kind == "count":
            days = _count_days(m.group())
        else:  # neg, skip
            continue
        buckets |= {_onset_bucket(d) for d in days}
    return buckets


def _count_days(phrase: str) -> list[float]:
    m = _COUNT_RE.fullmatch(phrase)
    if m is None:
        return []
    unit = _UNIT_DAYS[m["unit"].lower()]
    extra = 1 if m["more"] else 0
    return [_number(n) * unit + extra for n in (m["a"], m["b"] or m["c"]) if n]


def _number(phrase: str) -> int:
    for word in reversed(phrase.lower().split()):
        if word.isdigit():
            return int(word)
        if word in _NUMBER_WORDS:
            return _NUMBER_WORDS[word]
    return 0


def _onset_bucket(days: float) -> str:
    days = int(days)  # hours -> whole days: "a few hours" is today
    return "today" if days <= 0 else "1_3_days" if days <= 3 else "4_7_days" if days <= 7 else "over_7_days"
