"""Task A3: personal-data filter (PV-01). Synthetic people, 555-01xx phones, @example.com emails, invented places."""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from sentinel_contract import SCHEMA_DIR
from sentinel_patient import filter as pfilter
from sentinel_patient.filter import PLACEHOLDERS, Redaction, redact

APP_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def engine():
    pfilter.warm_up()  # loads spaCy once for the module (a few seconds)


def check(text: str, removed: list[str], placeholder: str, kept: tuple[str, ...] = ()) -> Redaction:
    r = redact(text)
    for value in removed:
        assert value not in r.text, f"{value!r} survived"
    assert f"[{placeholder}]" in r.text
    assert placeholder in r.entity_types
    for word in kept:
        assert word in r.text, f"{word!r} was redacted"
    return r


# --- Each identifier type is removed ----------------------------------------------------------------------------
@pytest.mark.parametrize("text, removed", [
    ("Hi, this is Walter Brennan, my rash is back.", ["Walter", "Brennan"]),
    ("My daughter Anna Kowalski drove me in, I felt sick during the drip.", ["Anna", "Kowalski"]),
    ("I'm calling for my mother, Margaret, her ankles are puffy.", ["Margaret"]),
    ("my son jake has itchy bumps since tuesday.", ["jake"]),
    ("my name is edith clarke and I'm tired.", ["edith", "clarke"]),
    ("Dr. Okafor said the dry skin is mild.", ["Okafor"]),
    ("walter here, sore mouth today.", ["walter"]),
])
def test_removes_names(text, removed):
    check(text, removed, "NAME")


@pytest.mark.parametrize("text, removed", [
    ("I live at 42 Maple Street, Apt 3B and the rash started yesterday.", ["42", "Maple", "3B"]),
    ("i live on 12 oak lane, coughing since monday.", ["12 oak", "oak lane"]),
    ("Send it to 1450 Ocean Drive, Suite 200, FL 33139 please.", ["1450", "Ocean", "200", "33139"]),
    ("My zip code is 62704 and I have loose stools.", ["62704"]),
    ("Write to PO Box 77, I'm worn out.", ["77"]),
    ("I live with my wife in apartment 12 at 77 Harbor View Road.", ["apartment 12", "77", "Harbor"]),
])
def test_removes_street_addresses(text, removed):
    check(text, removed, "ADDRESS")


@pytest.mark.parametrize("text, removed", [
    ("My phone is 555-0142 if you need me.", ["555", "0142"]),
    ("Call (617) 555-0199 after lunch.", ["617", "0199"]),
    ("Text me on +16175550199 tomorrow.", ["6175550199"]),
    ("My son is on 555 0177.", ["0177"]),
    ("Office 617.555.0123, rash is mild.", ["0123"]),
    ("Reach me at five five five oh one four two.", ["five five five"]),
])
def test_removes_phone_numbers(text, removed):
    check(text, removed, "PHONE")


@pytest.mark.parametrize("text, removed", [
    ("Email anna.k@example.com with the results.", ["anna.k", "example.com"]),
    ("It's WALTER@EXAMPLE.COM in capitals.", ["WALTER", "EXAMPLE"]),
    ("my email is edith dot clarke at example dot com thanks", ["edith", "clarke", "example"]),
])
def test_removes_emails(text, removed):
    check(text, removed, "EMAIL")


@pytest.mark.parametrize("text, removed", [
    ("I was born on March 12, 1934 and have a cough.", ["March 12", "1934"]),
    ("My DOB is 03/12/1934.", ["03/12", "1934"]),
    ("Date of birth: 12 March 1934. Rash since Monday.", ["12 March", "1934"]),
    ("Birth date 1934-03-12, I'm tired.", ["1934", "03-12"]),
    ("I'm 82, born in 1944, out of breath today.", ["1944"]),
    ("my birthday is june 3rd and my nails are sore.", ["june 3rd"]),
    ("Born 7/4/52. Felt sick during the drip.", ["7/4/52"]),
])
def test_removes_dates_of_birth(text, removed):
    check(text, removed, "DATE_OF_BIRTH")


@pytest.mark.parametrize("text, removed", [
    ("She drove me to Lakeside Emergency Hospital last night.", ["Lakeside"]),
    ("Picked up pills at Northgate Pharmacy in Boston, Massachusetts.", ["Northgate", "Boston", "Massachusetts"]),
    ("Dr. Okafor at St. Mary's Clinic saw me.", ["Mary"]),
    ("I went to lakeside hospital on Friday.", ["lakeside"]),
    ("Mouth ulcers since I got back from Toronto, Canada.", ["Toronto", "Canada"]),
    ("We moved from Ohio to Springfield, coughing a lot.", ["Ohio", "Springfield"]),
    ("My doctor is at Riverside Medical Center.", ["Riverside"]),
])
def test_removes_place_names(text, removed):
    check(text, removed, "PLACE")


@pytest.mark.parametrize("text, removed", [
    ("My SSN is 078-05-1120.", ["078-05-1120", "1120"]),
    ("My patient number is MRN 4471923.", ["4471923"]),
    ("Medicare number 1EG4-TE5-MK72.", ["1EG4", "MK72"]),
])
def test_removes_id_numbers(text, removed):
    check(text, removed, "ID")


def test_identifier_heavy_paragraph_leaves_no_fragment():
    text = ("Hi, this is Walter Brennan, I live at 42 Maple Street, Apt 3B, Springfield, IL 62704. My phone is "
            "555-0142 and my daughter Anna Kowalski is on (617) 555-0199 or anna.k@example.com. I was born on "
            "March 12, 1934. She drove me to Lakeside Emergency Hospital. I've had a moderate rash since Monday "
            "and loose stools for two days.")
    r = redact(text)
    for fragment in ("Walter", "Brennan", "42", "Maple", "3B", "Springfield", "62704", "555", "0142", "Anna",
                     "Kowalski", "617", "0199", "example", "March 12", "1934", "Lakeside"):
        assert fragment not in r.text, f"{fragment!r} survived"
    for kept in ("moderate rash since Monday", "loose stools for two days"):
        assert kept in r.text
    assert r.entity_types == ("ADDRESS", "DATE_OF_BIRTH", "EMAIL", "NAME", "PHONE", "PLACE")


# --- What extraction needs is kept -------------------------------------------------------------------------------
def _schema_phrases() -> list[str]:
    terms = json.loads((SCHEMA_DIR / "terms.json").read_text())["terms"]
    return sorted({p for t in terms if t["term_code"] != "SE_OTHER_REVIEW"
                   for p in [t["label_term"], *t["everyday_words"]]})


@pytest.mark.parametrize("phrase", _schema_phrases())
def test_keeps_every_symptom_word_from_the_term_list(phrase):
    for text in (f"{phrase[0].upper()}{phrase[1:]} since yesterday.", f"Walter says: {phrase}, mild, today."):
        r = redact(text)
        assert phrase.lower() in r.text.lower(), f"{phrase!r} was redacted"


@pytest.mark.parametrize("text", [
    "Tired and worn out since yesterday. Mild cough last week. No energy, about a week now.",
    "Rash on my arms today. Sore mouth for 3 days. Swollen ankles since last Tuesday.",
    "Diarrhea started two days ago, pretty severe, then it got worse since Monday.",
    "Out of breath this morning, it's moderate. Not hungry over the weekend.",
    "I was feeling Tired, Worn Out, No Energy. Rash Is Bad. Severe Diarrhea.",
    "Since March 3 I've had loose stools, it's a 7 out of 10, really bad.",
    "My baby was born 3 weeks ago and has a rash since yesterday.",
    "I've been dizzy since my birthday last week.",
    "I take 2 tablets at 8 am, felt sick during the drip on Tuesday, chills at infusion.",
])
def test_keeps_symptom_severity_and_relative_onset_words(text):
    r = redact(text)
    assert r.text == text
    assert r.entity_types == ()


def test_keeps_relative_onset_next_to_identifiers():
    r = redact("Walter Brennan here: I've had a severe rash since Monday and diarrhea two days ago.")
    assert r.text == "[NAME] here: I've had a severe rash since Monday and diarrhea two days ago."


# --- Output contract ---------------------------------------------------------------------------------------------
def test_entity_types_are_sorted_placeholder_names_never_values():
    text = "Edith Clarke, 555-0142, edith@example.com, 9 Birch Road, born 1940, Lakeside Hospital."
    r = redact(text)
    assert r.entity_types == tuple(sorted(set(r.entity_types)))
    assert set(r.entity_types) <= set(PLACEHOLDERS)
    for value in ("Edith", "Clarke", "555-0142", "edith@example.com", "Birch", "1940", "Lakeside"):
        assert all(value not in t for t in r.entity_types)
        assert value not in r.text


def test_redaction_is_idempotent_and_frozen():
    first = redact("Hi it's Bob from Ohio, call 555-0142, rash since Monday.")
    assert first.text == "Hi it's [NAME] from [PLACE], call [PHONE], rash since Monday."
    assert redact(first.text).text == first.text
    with pytest.raises(AttributeError):
        first.text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_empty_text_is_returned_unchanged(text):
    assert redact(text) == Redaction(text=text, entity_types=())


def test_never_logs_or_prints_text(caplog, capsys):
    caplog.set_level(logging.DEBUG)
    redact("My daughter Anna Kowalski on 555-0199 says my rash is worse since Monday.")
    out = capsys.readouterr()
    for word in ("Anna", "Kowalski", "0199", "rash", "Monday"):
        assert word not in caplog.text
        assert word not in out.out + out.err


def test_import_is_cheap():
    code = ("import sys, sentinel_patient.filter; "
            "heavy = {'presidio_analyzer', 'spacy', 'en_core_web_lg'} & set(sys.modules); "
            "assert not heavy, heavy")
    subprocess.run([sys.executable, "-c", code], cwd=APP_DIR, check=True)


def test_never_downloads_a_spacy_model(monkeypatch):
    import spacy

    monkeypatch.setattr(spacy.util, "is_package", lambda name: False)
    monkeypatch.setattr(spacy.cli, "download", lambda *a, **k: pytest.fail("tried to download a model"))
    with pytest.raises(RuntimeError, match="not installed"):
        pfilter._build_engine()
