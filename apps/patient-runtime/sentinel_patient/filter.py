"""Personal-data filter, applied before extraction (PV-01). All local: Presidio + spaCy + regular expressions.

`redact(text)` replaces names, addresses, phone numbers, emails, dates of birth, place names and ID numbers with
placeholders ([NAME], [ADDRESS], [PHONE], [EMAIL], [DATE_OF_BIRTH], [PLACE], [ID]) so the local model only ever
sees filtered text. What extraction needs is kept: symptom words (allow-list built from schema/terms.json),
severity words and relative time phrases ("two days ago", "since Monday"); only dates of birth are redacted,
never relative dates.

How it works:
- Presidio AnalyzerEngine with spaCy `en_core_web_lg`, configured explicitly (never downloaded at runtime), plus
  Presidio's default pattern recognizers (email, phone, SSN, credit card, ...) and our own pattern recognizers
  for street addresses, short phone numbers, spoken emails, facility names, US states, IDs and dates with a year.
- Presidio DATE_TIME results are kept as text unless they are a calendar date with a year or sit next to a birth
  word ("born", "birthday", "DOB"); a regex catches dates after a birth word that spaCy misses.
- Name and place guesses (spaCy, heuristics) have protected words trimmed from their edges, so a symptom or
  severity word is never redacted; guesses made only of generic words ("Hospital", "DOB") are dropped.
- Overlapping spans are merged and widened to whole words, so no fragment of an identifier survives.

Never logs or prints text. The engine is built once on first use; `warm_up()` builds it ahead of time.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass

SPACY_MODEL = "en_core_web_lg"
MIN_SCORE = 0.4  # drops Presidio's "very weak" guesses (bank / licence / passport numbers at 0.01-0.1)

NAME, ADDRESS, PHONE, EMAIL, DATE_OF_BIRTH, PLACE, ID = (
    "NAME", "ADDRESS", "PHONE", "EMAIL", "DATE_OF_BIRTH", "PLACE", "ID")
PLACEHOLDERS = (NAME, ADDRESS, PHONE, EMAIL, DATE_OF_BIRTH, PLACE, ID)


@dataclass(frozen=True)
class Redaction:
    text: str                      # input with every identifier replaced by a placeholder
    entity_types: tuple[str, ...]  # sorted unique placeholder types found, e.g. ("EMAIL", "NAME"); never values


def redact(text: str) -> Redaction:
    """Replace every identifier in `text` with a placeholder. Pure: no logging, no I/O beyond the cached engine."""
    if not text or not text.strip():
        return Redaction(text=text, entity_types=())
    spans = _merge(_detect(text), text)
    out, pos = [], 0
    for start, end, label in spans:
        out.append(text[pos:start])
        out.append(f"[{label}]")
        pos = end
    out.append(text[pos:])
    return Redaction(text="".join(out), entity_types=tuple(sorted({label for _, _, label in spans})))


def warm_up() -> None:
    """Load spaCy and build the analyzer now (a few seconds) instead of on the first `redact` call."""
    _engine()


# --- Entity types -> placeholders -------------------------------------------------------------------------------
# Custom recognizers use SS_* entity names. Priority breaks ties between overlapping spans of equal length.
_ENTITY_MAP: dict[str, tuple[str, int]] = {
    "EMAIL_ADDRESS": (EMAIL, 9), "SS_EMAIL": (EMAIL, 9),
    "US_SSN": (ID, 8), "SS_SSN": (ID, 8),
    "PHONE_NUMBER": (PHONE, 7), "SS_PHONE": (PHONE, 7),
    "SS_DOB": (DATE_OF_BIRTH, 6),
    "SS_ADDRESS": (ADDRESS, 5),
    "SS_ID": (ID, 4),
    "SS_NAME": (NAME, 3), "PERSON": (NAME, 2),
    "SS_PLACE": (PLACE, 2), "LOCATION": (PLACE, 1), "ORGANIZATION": (PLACE, 1),
}
_DEFAULT_ID = (ID, 4)              # any other Presidio identifier (credit card, IBAN, IP, URL, licence, ...)
_NOT_IDENTIFIERS = {"NRP"}         # nationality / religion / political group: not on the PV-01 list
_GUESSES = {"PERSON", "LOCATION", "ORGANIZATION", "SS_NAME", "SS_PLACE"}  # trimmed with the allow-list

_NLP_CONFIGURATION = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
    "ner_model_configuration": {
        "model_to_presidio_entity_mapping": {
            "PERSON": "PERSON", "PER": "PERSON", "GPE": "LOCATION", "LOC": "LOCATION", "FAC": "LOCATION",
            "ORG": "ORGANIZATION", "NORP": "NRP", "DATE": "DATE_TIME", "TIME": "DATE_TIME",
        },
        # ORG is kept on purpose (hospitals, clinics, pharmacies); its false positives are trimmed below.
        "labels_to_ignore": ["CARDINAL", "EVENT", "LANGUAGE", "LAW", "MONEY", "ORDINAL", "PERCENT", "PRODUCT",
                             "QUANTITY", "WORK_OF_ART"],
        "low_score_entity_names": [],
    },
}

# --- Words that must survive (allow-list) -----------------------------------------------------------------------
_SEVERITY_WORDS = {
    "mild", "mildly", "moderate", "moderately", "severe", "severely", "slight", "slightly", "little", "bit",
    "bad", "badly", "worse", "worst", "better", "terrible", "terribly", "awful", "horrible", "unbearable", "very",
    "really", "quite", "pretty", "extremely", "so", "too", "okay", "ok", "fine", "much", "lot",
}
_TIME_WORDS = {
    "today", "tonight", "yesterday", "tomorrow", "now", "ago", "since", "last", "past", "this", "next", "about",
    "around", "almost", "nearly", "over", "under", "recently", "lately", "earlier", "morning", "afternoon",
    "evening", "night", "weekend", "day", "days", "week", "weeks", "fortnight", "month", "months", "hour", "hours",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "couple", "few", "several",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "started", "began", "start",
}
_EXTRA_SYMPTOM_WORDS = {  # common complaints outside the term list (they map to SE_OTHER_REVIEW, so keep them)
    "headache", "headaches", "migraine", "nausea", "nauseous", "sick", "vomiting", "vomit", "throwing", "fever",
    "feverish", "temperature", "chills", "dizzy", "dizziness", "lightheaded", "faint", "pain", "painful", "ache",
    "aches", "aching", "sore", "itch", "itchy", "itching", "swollen", "swelling", "bleeding", "bruising", "cramps",
    "cramping", "constipation", "constipated", "numb", "numbness", "tingling", "blurry", "blurred", "vision",
    "insomnia", "sleep", "sleepy", "weak", "weakness", "breathless", "wheezing", "wheezy", "chest", "palpitations",
    "heartburn", "bloated", "bloating", "acne", "pimples", "blisters", "peeling", "hives", "eyes", "hair",
    "confused", "confusion", "anxious", "anxiety", "depressed", "low", "mood",
}
_TRIM_EXTRA = {  # non-identifying words that NER sometimes glues onto a name or place
    "the", "a", "an", "my", "our", "your", "his", "her", "their", "i", "me", "and", "or", "at", "in", "on", "to",
    "mr", "mrs", "ms", "miss", "mx", "dr", "doctor", "nurse", "prof", "hi", "hello", "hey", "thanks", "yes", "no",
    "then", "also", "after", "before", "went", "from", "into", "via", "near", "by", "with", "for", "of", "local",
    "nearest", "visit", "visited", "visiting", "called", "named",
    "name", "address", "phone", "email", "date_of_birth", "place", "id",  # placeholder words (redact is idempotent)
}
_GENERIC_WORDS = {  # a guess made only of these (plus trimmed words) is not an identifier
    "hospital", "hospitals", "clinic", "clinics", "pharmacy", "pharmacies", "medical", "center", "centre",
    "health", "healthcare", "care", "urgent", "emergency", "infirmary", "hospice", "surgery", "group", "oncology",
    "cancer", "department", "ward", "unit", "er", "icu", "ed", "gp", "md", "rn", "np", "dob", "ssn", "mrn",
    "medicare", "medicaid", "insurance", "covid", "covid-19", "tv", "st", "saint",
}
_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _schema_words() -> set[str]:
    """Words from schema/terms.json (label_term, everyday_words) and drug names: never redacted."""
    from sentinel_contract import SCHEMA_DIR

    words: set[str] = set()
    for term in json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]:
        if term["term_code"] == "SE_OTHER_REVIEW":
            continue  # "Other, needs review" is not something a patient says
        for phrase in [term["label_term"], *term["everyday_words"], *term.get("drug_scope", [])]:
            words |= {w.lower() for w in _TOKEN_RE.findall(phrase)}
    return words


# --- Regular expressions used outside Presidio ------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
          r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_YEAR = r"(?:1[89]\d{2}|20\d{2})"
_YEAR_RE = re.compile(rf"\b{_YEAR}\b")
_MONTH_RE = re.compile(rf"(?i)\b{_MONTH}\b")
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,4}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b")
_FULL_NUMERIC_DATE_RE = re.compile(r"\b\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}\b")
_ORDINAL_DAY_RE = re.compile(r"(?i)\b\d{1,2}(?:st|nd|rd|th)\b")
_RELATIVE_RE = re.compile(
    r"(?i)\b(?:ago|last|past|previous|yesterday|today|tonight|tomorrow|this|next|since|recent|recently|now|"
    r"earlier|later|days?|weeks?|months?|hours?|weekend|morning|afternoon|evening|night)\b")
_BIRTH_CUE_RE = re.compile(
    r"(?i)\b(?:born|birth\s*days?|bday|b-day|birth\s*date|date\s+of\s+birth|d\.?\s?o\.?\s?b)(?![a-z])")
_DATEISH_RE = re.compile(
    rf"(?i)\b(?:{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{2,4}})?\b"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b\.?(?:,?\s+\d{{2,4}}\b)?"
    rf"|(?:the\s+)?\d{{1,2}}(?:st|nd|rd|th)\b(?:\s+of\s+{_MONTH}\b)?"
    rf"|\d{{1,4}}[/.-]\d{{1,2}}(?:[/.-]\d{{2,4}})?\b"
    rf"|{_YEAR}\b"
    rf"|{_MONTH}\b)")
_SENTENCE_END_RE = re.compile(r"[.!?\n](?:\s|$)")
_CUE_WINDOW_BEFORE, _CUE_WINDOW_AFTER = 40, 30


# --- Custom Presidio pattern recognizers ------------------------------------------------------------------------
_WEEKDAY_OR_MONTH = r"(?:" + "|".join(d.capitalize() for d in _WEEKDAYS + _MONTHS) + r")\b"
_CAP_NAME = rf"(?!{_WEEKDAY_OR_MONTH})[A-Z][a-zA-Z'’-]+(?:\s+(?!{_WEEKDAY_OR_MONTH})[A-Z][a-zA-Z'’-]+)?"
_RELATIONS = (r"son|daughter|wife|husband|partner|mother|mom|mum|mommy|mummy|father|dad|daddy|brother|sister|"
              r"grandson|granddaughter|grandma|grandpa|granny|grandmother|grandfather|aunt|auntie|uncle|niece|"
              r"nephew|friend|neighbou?r|nurse|doctor|caregiver|carer|baby|child|kid|boy|girl|cousin|fianc[eé]e?|"
              r"boyfriend|girlfriend|stepson|stepdaughter|twin")
_NAME_STOP = (r"(?:and|but|i|im|i'm|my|the|a|so|from|here|with|since|have|has|had|was|is|for|to|of|in|on|at|or|"
              r"said|says|who|will|been|speaking|calling)\b")
_LOWER_NAME_STOP = (  # after "my son" etc. in lowercase text: words that are clearly not a name
    rf"(?:{_RELATIONS}|and|but|i|im|i'm|my|me|the|a|an|so|from|here|there|with|since|have|has|had|was|is|are|were|"
    r"be|been|for|to|of|in|on|at|or|who|which|that|when|will|would|can|could|should|may|might|must|also|just|"
    r"always|never|often|still|too|now|again|today|yesterday|said|says|say|got|gets|get|took|takes|take|drove|"
    r"drives|came|comes|went|goes|saw|sees|told|tells|thinks|think|thought|noticed|notices|helps|helped|brought|"
    r"brings|keeps|kept|wants|wanted|needs|needed|feels|felt|does|did|doesn't|didn't|isn't|wasn't|hasn't|can't|"
    r"won't|asked|asks|made|makes|found|finds|looks|looked|seems|seemed|gave|gives|put|puts|lives|lived|stays|"
    r"stayed|works|worked|calls|texted|answered|answers|speaking|calling)\b")
_STREET_SUFFIX = (r"(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|place|pl|way|terrace|"
                  r"ter|circle|cir|parkway|pkwy|highway|hwy|square|sq|trail|trl|crescent|cres|close|row|alley|loop|"
                  r"path|pike|plaza|walk|mews|grove|gardens|heights|hill)")
_STREET_SUFFIX_LOWER = r"(?:street|avenue|road|lane|drive|boulevard|court|terrace|parkway|highway|crescent|close)"
_NUM_STOP = (r"(?:days?|hours?|weeks?|months?|years?|times?|minutes?|mins?|of|in|on|the|a|an|at|to|for|or|and|"
             r"pills?|tablets?|doses?|mg|ml|more|less|nights?|am|pm|o'clock)\b")
_FACILITY = (r"(?i:hospital|clinic|medical\s+cent(?:er|re)|health\s+cent(?:er|re)|cancer\s+cent(?:er|re)|"
             r"care\s+cent(?:er|re)|medical\s+group|pharmacy|drug\s?store|chemist|infirmary|hospice|surgery|"
             r"urgent\s+care|health(?:care)?|medical|cent(?:er|re))")
_FACILITY_LOWER = r"(?:hospital|clinic|pharmacy|infirmary|hospice|medical\s+cent(?:er|re))"
_FACILITY_STOP = (r"(?:the|a|an|my|your|his|her|our|their|this|that|local|nearest|nearby|same|new|old|big|small|"
                  r"main|general|emergency|children's|kids|day|walk-in|eye|cancer|infusion|community|chemo|"
                  r"oncology|mental|dental|vet|to|at|in|from|of|for|and|or|went|go|going|been|was|is|back|next|"
                  r"other|another|any|some|no|private|public|university|teaching|rehab|city|county|state)\b")
_STREET_STOP = (r"(?:the|a|an|my|your|his|her|our|their|this|that|same|other|another|long|rough|bumpy|busy|wrong|"
                r"right|whole|open|dirt|back|side|toll|to|at|in|on|from|of|for|and|or|down|up|across|along|by)\b")
_US_STATES = (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
    "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
    "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
)
_DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
_TLD = r"(?i:com|org|net|edu|gov|io|co|uk|us|ca|info|me|biz)"

_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "SS_EMAIL": [  # spoken form: "walter dot b at example dot com"
        ("spoken_email", rf"(?<![\w+.-])[\w+-]+(?:(?:\.|\s+(?i:dot)\s+)[\w+-]+){{0,4}}\s+(?i:at)\s+[\w-]+"
                         rf"(?:(?:\.|\s+(?i:dot)\s+)[\w-]+){{0,3}}(?:\.|\s+(?i:dot)\s+){_TLD}\b"),
    ],
    "SS_SSN": [("ssn", r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")],
    "SS_PHONE": [
        ("us_10_digit", r"(?<![\w+])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"),
        ("local_7_digit", r"(?<![\w-])\d{3}[\s.-]\d{4}(?![\w-])"),
        ("international", r"(?<![\w+])\+(?:[\s.()-]*\d){7,15}(?!\w)"),
        ("spaced_digits", r"\b\d(?:[\s.-]\d){6,14}\b"),
        ("spoken_digits", rf"(?i)\b{_DIGIT_WORD}(?:[\s,.-]+{_DIGIT_WORD}){{6,}}\b"),
    ],
    "SS_DOB": [  # calendar dates that include a year (birth-word context is handled in Python)
        ("month_day_year", rf"(?i)\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+{_YEAR}\b"),
        ("day_month_year", rf"(?i)\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\.?,?\s+{_YEAR}\b"),
        ("month_year", rf"(?i)\b{_MONTH}\.?,?\s+(?:of\s+)?{_YEAR}\b"),
        ("numeric_dmy_mdy", r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:\d{4}|\d{2})\b"),
        ("numeric_ymd", rf"\b{_YEAR}[/.-]\d{{1,2}}[/.-]\d{{1,2}}\b"),
    ],
    "SS_ADDRESS": [
        ("street", rf"\b\d{{1,6}}[A-Za-z]?(?:\s+(?:[NSEW]\.?|North|South|East|West))?"
                   rf"(?:\s+(?:[A-Z][\w'’-]*|\d+(?i:st|nd|rd|th))){{1,4}}\s+(?i:{_STREET_SUFFIX})\b\.?"),
        ("street_lower", rf"\b\d{{1,6}}[a-z]?\s+(?!{_NUM_STOP})[a-z][\w'’-]*(?:\s+[a-z][\w'’-]*){{0,2}}"
                         rf"\s+{_STREET_SUFFIX_LOWER}\b"),
        ("after_live_cue", r"(?<=\b(?i:live|lives|living|stay|stays|staying|moved|address\s+is)\s+(?i:at|on|to|"
                           r"is)?\s*)\d{1,6}[A-Za-z]?\s+[A-Za-z][\w'’-]*"
                           r"(?:\s+(?!(?i:and|but|with|since|in|for|near|so|because|i|my)\b)[A-Za-z][\w'’-]*){0,3}"),
        ("unit", r"\b(?i:apartment|apt|unit|suite|ste|flat|room|rm)\.?\s*#?\s*(?:\d+[A-Za-z]?|[A-Za-z]\d*)\b"
                 r"|(?<!\w)#\s?\d+[A-Za-z]?\b"),
        ("po_box", r"\b(?i:p\.?\s?o\.?\s*box)\s+\d+\b"),
        ("state_zip", r"\b[A-Z]{2},?\s+\d{5}(?:-\d{4})?\b"),
        ("uk_postcode", r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"),
        ("zip", r"(?<![\w$.,-])\d{5}(?:-\d{4})?(?![\w.,-]|\s*(?i:steps|mg|mcg|ml|units|iu|calories|feet|ft|"
                r"miles|meters|people|dollars|bucks)\b)"),
    ],
    "SS_ID": [
        ("alnum_with_4_digits", r"\b(?=(?:[A-Za-z-]*\d){4})[A-Za-z0-9][A-Za-z0-9-]{5,}[A-Za-z0-9]\b"),
        ("after_id_cue", r"(?<=\b(?i:member|policy|insurance|medicare|medicaid|account|patient|record|chart|mrn|"
                         r"social\s+security|licen[cs]e|passport|nhs|id)\s*(?i:number|no\.?|num|#|id)?\s*"
                         r"(?i:is|:|=)?\s*)(?=[A-Za-z-]*\d)[A-Za-z0-9][A-Za-z0-9-]{3,}\b"),
    ],
    "SS_NAME": [
        ("title", rf"(?<=\b(?i:dr|doctor|mr|mrs|ms|miss|mx|nurse|prof|professor|pastor|rev)\.?\s+){_CAP_NAME}"),
        ("self_intro", rf"(?<=\b(?i:my\s+name\s+is|my\s+name's|name\s+is|i\s+am|i'm|this\s+is|it's|call\s+me|"
                       rf"called|named)\s+){_CAP_NAME}"),
        ("self_intro_lower", rf"(?<=\b(?i:my\s+name\s+is|my\s+name's|call\s+me)\s+)(?!{_NAME_STOP})[a-z][a-z'’-]+"
                             rf"(?:\s+(?!{_NAME_STOP})[a-z][a-z'’-]+)?"),
        ("relation", rf"(?<=\b(?i:my|our|his|her|their)\s+(?i:{_RELATIONS}),?\s+){_CAP_NAME}"),
        ("relation_lower", rf"(?<=\b(?i:my|our|his|her|their)\s+(?i:{_RELATIONS}),?\s+)(?!{_LOWER_NAME_STOP})"
                           rf"(?![a-z]+ing\b)[a-z][a-z'’-]+(?:\s+(?!{_LOWER_NAME_STOP})(?![a-z]+ing\b)[a-z][a-z'’-]+)?"),
    ],
    "SS_PLACE": [
        ("facility", rf"\b(?:(?:St|Mt|Saint|Mount)\.?\s+)?(?:[A-Z][\w'’&-]*\.?\s+){{1,4}}{_FACILITY}\b"),
        ("facility_lower", rf"\b(?!{_FACILITY_STOP})[a-z][\w'’-]*(?:\s+[a-z][\w'’-]*)?\s+{_FACILITY_LOWER}\b"),
        ("street_name", r"\b(?:[A-Z][\w'’-]*\s+){1,3}(?:Street|Avenue|Ave\.?|Road|Rd\.?|Lane|Boulevard|Blvd\.?|Drive|"
                        r"Terrace|Parkway|Highway)\b"),
        ("street_name_lower", rf"\b(?!{_STREET_STOP})[a-z][\w'’-]*\s+(?:street|avenue|road|lane|boulevard)\b"),
    ],
}


def _custom_recognizers():
    from presidio_analyzer import Pattern, PatternRecognizer

    flags = re.MULTILINE  # case-sensitive by default; patterns opt in with (?i:...) (Presidio compiles with `regex`)
    recognizers = [
        PatternRecognizer(supported_entity=entity, name=f"SafeSignal_{entity}", global_regex_flags=flags,
                          patterns=[Pattern(name, rx, 0.9) for name, rx in patterns])
        for entity, patterns in _PATTERNS.items()
    ]
    states = [*_US_STATES, *(s.lower() for s in _US_STATES)]
    recognizers.append(PatternRecognizer(supported_entity="SS_PLACE", name="SafeSignal_US_STATES",
                                         global_regex_flags=flags, deny_list=states, deny_list_score=0.9))
    return recognizers


# --- Engine (built once, lazily) --------------------------------------------------------------------------------
_lock = threading.Lock()
_state: dict = {}


def _engine():
    engine = _state.get("engine")
    if engine is None:
        with _lock:
            engine = _state.get("engine")
            if engine is None:
                engine = _state["engine"] = _build_engine()
    return engine


def _build_engine():
    import spacy
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    # Presidio's DEBUG messages include context words from the text: keep them off even if the app logs DEBUG.
    logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)
    if not spacy.util.is_package(SPACY_MODEL):  # Presidio would otherwise try to download it
        raise RuntimeError(f"spaCy model {SPACY_MODEL} is not installed; install it as a package (uv sync)")
    nlp_engine = NlpEngineProvider(nlp_configuration=_NLP_CONFIGURATION).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp_engine, countries=["us"])
    for recognizer in _custom_recognizers():
        registry.add_recognizer(recognizer)
    _state["trim_words"] = frozenset(
        _schema_words() | _SEVERITY_WORDS | _TIME_WORDS | _EXTRA_SYMPTOM_WORDS | _TRIM_EXTRA)
    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=["en"])


# --- Detection --------------------------------------------------------------------------------------------------
Span = tuple[int, int, str, int]  # start, end, placeholder, priority


def _detect(text: str) -> list[Span]:
    engine = _engine()
    trim_words = _state["trim_words"]
    spans: list[Span] = []
    for r in engine.analyze(text=text, language="en", score_threshold=MIN_SCORE):
        if r.entity_type in _NOT_IDENTIFIERS:
            continue
        if r.entity_type == "DATE_TIME":
            if _is_birth_date(text, r.start, r.end):
                spans.append((r.start, r.end, DATE_OF_BIRTH, 6))
            continue
        start, end = r.start, r.end
        if r.entity_type in _GUESSES:
            trimmed = _trim(text, start, end, trim_words)
            if trimmed is None:
                continue
            start, end = trimmed
        label, priority = _ENTITY_MAP.get(r.entity_type, _DEFAULT_ID)
        spans.append((start, end, label, priority))
    spans.extend(_birth_cue_dates(text))
    return spans


def _trim(text: str, start: int, end: int, trim_words: frozenset[str]) -> tuple[int, int] | None:
    """Strip allow-listed words from the edges of a name/place guess; None if nothing identifying is left."""
    tokens = list(_TOKEN_RE.finditer(text, start, end))

    def norm(m: re.Match) -> str:
        return re.sub(r"['’]s$", "", m.group().lower())

    while tokens and norm(tokens[0]) in trim_words:
        tokens.pop(0)
    while tokens and norm(tokens[-1]) in trim_words:
        tokens.pop()
    if not tokens or all(norm(t) in _GENERIC_WORDS or norm(t) in trim_words or t.group().isdigit() for t in tokens):
        return None
    return tokens[0].start(), tokens[-1].end()


def _sentence_window(text: str, start: int, end: int) -> tuple[int, int]:
    lo = max(0, start - _CUE_WINDOW_BEFORE)
    for m in _SENTENCE_END_RE.finditer(text, lo, start):
        lo = m.end()
    hi = min(len(text), end + _CUE_WINDOW_AFTER)
    m = _SENTENCE_END_RE.search(text, end, hi)
    return lo, (m.start() if m else hi)


def _is_birth_date(text: str, start: int, end: int) -> bool:
    """A date-time span is a date of birth if it is a calendar date with a year, or an absolute date near a
    birth word. Relative phrases ("two days ago", "since Monday", "last week") are never redacted."""
    s = text[start:end]
    if _FULL_NUMERIC_DATE_RE.search(s) or (_YEAR_RE.search(s) and (_MONTH_RE.search(s) or
                                                                    _NUMERIC_DATE_RE.search(s))):
        return True
    if _RELATIVE_RE.search(s):
        return False
    if not (_MONTH_RE.search(s) or _NUMERIC_DATE_RE.search(s) or _YEAR_RE.search(s) or _ORDINAL_DAY_RE.search(s)):
        return False
    lo, hi = _sentence_window(text, start, end)
    return bool(_BIRTH_CUE_RE.search(text, lo, hi))


def _birth_cue_dates(text: str) -> list[Span]:
    """Dates right after a birth word ("born in 1934", "my birthday is June 3rd") that spaCy may miss."""
    spans = []
    for cue in _BIRTH_CUE_RE.finditer(text):
        _, hi = _sentence_window(text, cue.end(), cue.end())
        m = _DATEISH_RE.search(text, cue.end(), hi)
        if m and not _RELATIVE_RE.search(text, cue.end(), m.end()):
            spans.append((m.start(), m.end(), DATE_OF_BIRTH, 6))
    return spans


def _merge(spans: list[Span], text: str) -> list[tuple[int, int, str]]:
    """Widen spans to whole words, merge overlapping or touching spans, and label each merged span with its
    longest member (ties: higher priority)."""
    widened = []
    for start, end, label, priority in spans:
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        while end < len(text) and text[end].isalnum():
            end += 1
        if end > start:
            widened.append((start, end, label, priority))
    widened.sort(key=lambda s: (s[0], -s[1]))

    merged: list[tuple[int, int, str]] = []
    group_start = group_end = -1
    best: tuple[int, int, str] | None = None  # (length, priority, label)
    for start, end, label, priority in widened:
        if best is not None and start <= group_end:
            group_end = max(group_end, end)
            best = max(best, (end - start, priority, label))
            continue
        if best is not None:
            merged.append((group_start, group_end, best[2]))
        group_start, group_end, best = start, end, (end - start, priority, label)
    if best is not None:
        merged.append((group_start, group_end, best[2]))
    return merged
