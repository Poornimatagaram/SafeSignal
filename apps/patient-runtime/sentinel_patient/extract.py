"""Constrained extraction into coded fields (PV-02, SE-01, SE-02 groundwork, VC-10). Local model only.

`extract_symptoms(filtered_text)` asks the local Ollama model (default `llama3.2:3b`, temperature 0) for the
symptoms in an already filtered answer (see `filter.redact`). The output is forced into a JSON schema whose
term codes, severities and onsets are the enums in schema/, and is validated again here regardless of the model:
unknown code -> SE_OTHER_REVIEW (D-015), unstated or invalid severity -> None (re-asked later, VC-10), invalid
onset -> "unknown", duplicates dropped (first wins), at most 10 items.

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
    """JSON schema passed to Ollama's `format`: {"symptoms": [{term_code, severity, onset}]}."""
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
                        "severity": {"type": "string", "enum": [*_severities(), NOT_STATED]},
                        "onset": {"type": "string", "enum": list(_onsets())},
                    },
                    "required": ["term_code", "severity", "onset"],
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
Today is {weekday}."""

# Few-shot examples (Scoping Doc 17.2). Written for the prompt; never reuse them as evaluation cases.
_EXAMPLES = (
    ("I've had a really bad rash on my arms since yesterday. No diarrhea though.",
     [{"term_code": "SE_RASH", "severity": "severe", "onset": "1_3_days"}]),
    ("[NAME] here, I'm calling for my dad. He's been a bit tired for about a week, his ankles are puffy and he "
     "keeps getting headaches.",
     [{"term_code": "SE_FATIGUE", "severity": "mild", "onset": "4_7_days"},
      {"term_code": "SE_EDEMA", "severity": NOT_STATED, "onset": "unknown"},
      {"term_code": OTHER_REVIEW, "severity": NOT_STATED, "onset": "unknown"}]),
    ("She's off her food and her skin is flaky. She doesn't have a cough.",
     [{"term_code": "SE_DECREASED_APPETITE", "severity": NOT_STATED, "onset": "unknown"},
      {"term_code": "SE_DRY_SKIN", "severity": NOT_STATED, "onset": "unknown"}]),
    ("Feeling fine today, nothing new to report.", []),
)


def _messages(filtered_text: str) -> list[dict]:
    system = _SYSTEM_PROMPT.format(terms=_term_lines(), other=OTHER_REVIEW, not_stated=NOT_STATED,
                                   weekday=datetime.date.today().strftime("%A"))
    messages = [{"role": "system", "content": system}]
    for text, symptoms in _EXAMPLES:
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": json.dumps({"symptoms": symptoms})})
    messages.append({"role": "user", "content": filtered_text})
    return messages


# --- Errors and validation --------------------------------------------------------------------------------------
# Rules override the model (Scoping Doc 17.1): with no severity words at all, a severity is a guess (and a
# guessed "severe" would raise an alert), so it is dropped and re-asked (VC-10); likewise onset without time words.
_SEVERITY_CUE_RE = re.compile(
    r"(?i)\b(?:mild|mildly|moderate|moderately|severe|severely|slight|slightly|little|bit|bad|badly|worse|worst|"
    r"terrible|terribly|awful|horrible|unbearable|excruciating|extreme|extremely|very|really|quite|pretty|so|"
    r"super|a\s+lot|barely|hardly|can't|cannot|couldn't|unable|agony|killing|intense|serious|seriously)\b"
    r"|\b\d{1,2}\s*(?:/|out\s+of)\s*10\b")
_TIME_CUE_RE = re.compile(
    r"(?i)\b(?:today|tonight|yesterday|ago|since|recently|lately|started|starting|began|begun|overnight|weekend|"
    r"fortnight|days?|weeks?|months?|years?|hours?|morning|afternoon|evening|night|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b")

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


def _validate(data: dict, filtered_text: str = "") -> list[ExtractedSymptom]:
    codes, severities, onsets = set(term_codes()), set(_severities()), set(_onsets())
    if not _SEVERITY_CUE_RE.search(filtered_text):
        severities = set()
    if not _TIME_CUE_RE.search(filtered_text):
        onsets = {"unknown"}
    out: list[ExtractedSymptom] = []
    seen: set[str] = set()
    for item in data["symptoms"]:
        if not isinstance(item, dict):
            continue
        code = _clean(item.get("term_code"), str.upper)
        code = code if code in codes else OTHER_REVIEW
        if code in seen:
            continue
        severity = _clean(item.get("severity"), str.lower)
        onset = _clean(item.get("onset"), str.lower)
        seen.add(code)
        out.append(ExtractedSymptom(term_code=code, severity=severity if severity in severities else None,
                                    onset=onset if onset in onsets else "unknown"))
        if len(out) == MAX_SYMPTOMS:
            break
    return out


def _clean(value: Any, case) -> str | None:
    return case(value.strip()) if isinstance(value, str) else None
