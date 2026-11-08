"""Typed answers ("Type instead"): POST /checkin/turn/text runs the same steps as a spoken answer after the
transcript, and the session's input_mode (voice, text, mixed; D-066) reaches the summary and the sent record.

Fakes come from test_checkin_api; all names and numbers are synthetic.
"""

import logging

from test_checkin_api import (ANSWERS, FakeClient, FakePipeline, answer, fake_rate, make_client, restarted, rows,
                              start)


def typed(c, session_id, question_id, text, ask=0):
    return c.post("/checkin/turn/text", params={"session_id": session_id, "question_id": question_id, "ask": ask},
                  json={"text": text})


def mode_of(tmp_path, sid):
    return rows(tmp_path, "SELECT input_mode FROM checkin_session WHERE session_id = ?", sid)[0]["input_mode"]


def test_typed_answer_is_filtered_before_rating_and_extraction(tmp_path):
    seen_by_rater = []

    def rater(question, ask, text):
        seen_by_rater.append(text)
        return fake_rate(question, ask, text)

    c, pipeline, _ = make_client(tmp_path, rater=rater)
    with c:
        sid = start(c)
        r = typed(c, sid, "q1", "Walter here, I have an itchy rash")
    assert r.status_code == 200
    assert r.json() == {"transcript": "Walter here, I have an itchy rash",
                        "symptoms": [{"term_code": "SE_RASH", "label": "Rash", "severity": None, "onset": "unknown"}],
                        "extraction": "ok", "rating": "complete", "next": {"action": "next"}}
    assert seen_by_rater == ["[NAME] here, I have an itchy rash"]
    assert pipeline.model_saw == ["[NAME] here, I have an itchy rash"]


def test_typed_phone_number_is_redacted_before_the_model(tmp_path):
    pipeline = FakePipeline()
    redact = pipeline.redact
    pipeline.redact = lambda text: redact(text.replace("555-0199", "[PHONE]"))
    c, _, _ = make_client(tmp_path, pipeline=pipeline)
    with c:
        sid = start(c)
        assert typed(c, sid, "q2", "Call me on 555-0199, I have a rash").status_code == 200
    assert pipeline.model_saw == ["Call me on [PHONE], I have a rash"]


def test_typed_repeat_and_slower_are_commands(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        again = typed(c, sid, "q2", "repeat", ask=1).json()
        slower = typed(c, sid, "q2", "slower please", ask=1).json()
    assert (again["command"], again["next"], again["rating"]) == ("repeat", {"action": "repeat", "ask": 1}, None)
    assert (slower["command"], slower["next"]) == ("slower", {"action": "slower", "ask": 1})
    assert rows(tmp_path, "SELECT * FROM answer_turn") == [] and pipeline.model_saw == []


def test_typed_answer_rejects_bad_requests(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        assert typed(c, sid, "q1", "   \n ").status_code == 400
        assert typed(c, sid, "q1", "").json()["detail"] == "no answer typed"
        assert typed(c, sid, "q1", "a" * 1001).status_code == 422
        assert typed(c, sid, "q1", "a" * 1000).status_code == 200
        assert c.post("/checkin/turn/text", params={"session_id": sid, "question_id": "q1"},
                      json={"words": "x"}).status_code == 422
        assert c.post("/checkin/turn/text", params={"session_id": sid, "question_id": "q1"},
                      json={"text": 5}).status_code == 422
        assert typed(c, sid, "q1", "fine", ask=3).status_code == 422
        assert typed(c, sid, "Q1!", "fine").status_code == 422
        assert typed(c, "ses_zzzz", "q1", "fine").status_code == 422
        assert typed(c, "ses_00000000", "q1", "fine").status_code == 404
        assert typed(c, sid, "q99", "fine").status_code == 422
    assert len(rows(tmp_path, "SELECT * FROM answer_turn")) == 1


def test_typed_answer_from_another_machine_is_refused(tmp_path):
    c, pipeline, _ = make_client(tmp_path)
    with c:
        sid = start(c)
    remote, _, _ = make_client(tmp_path, pipeline=pipeline, client=("192.168.1.20", 50000))
    with remote:
        assert typed(remote, sid, "q1", "I have a rash").status_code == 403
    assert rows(tmp_path, "SELECT * FROM answer_turn") == [] and pipeline.model_saw == []


def test_typed_answer_to_a_shared_check_in_is_refused(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        for qid, text in ANSWERS:
            assert typed(c, sid, qid, text).status_code == 200
        assert c.post(f"/checkin/sessions/{sid}/approve", json={"severities": {}}).status_code == 200
        assert typed(c, sid, "q1", "one more").status_code == 409


def run_check_in(tmp_path, ways):
    """Answer the six questions, `ways[i]` = "voice" or "text"; return (summary record, sent record, sid)."""
    sentinel = FakeClient()
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = start(c)
        for (qid, text), way in zip(ANSWERS, ways):
            r = (answer if way == "voice" else typed)(c, sid, qid, text)
            assert r.status_code == 200, r.text
        summary = c.get(f"/checkin/sessions/{sid}/summary").json()
        assert c.post(f"/checkin/sessions/{sid}/approve", json={"severities": {}}).json()["status"] == "sent"
    return summary["share"]["record"], sentinel.sent[0], sid


def test_all_spoken_check_in_is_voice(tmp_path):
    shown, sent, sid = run_check_in(tmp_path, ["voice"] * 6)
    assert shown["input_mode"] == sent["input_mode"] == mode_of(tmp_path, sid) == "voice"


def test_all_typed_check_in_is_text(tmp_path):
    shown, sent, sid = run_check_in(tmp_path, ["text"] * 6)
    assert shown["input_mode"] == sent["input_mode"] == mode_of(tmp_path, sid) == "text"
    assert shown == sent


def test_one_spoken_and_the_rest_typed_is_mixed(tmp_path):
    shown, sent, sid = run_check_in(tmp_path, ["voice"] + ["text"] * 5)
    assert shown["input_mode"] == sent["input_mode"] == "mixed"


def test_mode_follows_the_first_answer_then_turns_mixed_and_stays_mixed(tmp_path):
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        assert typed(c, sid, "q2", "repeat").json()["command"] == "repeat"  # a command is not an answer
        assert answer(c, sid, "q2", "slower").json()["command"] == "slower"
        assert mode_of(tmp_path, sid) == "voice"  # the column default; no answer yet
        typed(c, sid, "q1", "I feel tired")
        assert mode_of(tmp_path, sid) == "text"
        typed(c, sid, "q2", "no rash")
        assert mode_of(tmp_path, sid) == "text"
        answer(c, sid, "q3", "It's moderate")
        assert mode_of(tmp_path, sid) == "mixed"
        typed(c, sid, "q4", "It started two days ago")
        assert mode_of(tmp_path, sid) == "mixed"


def test_mode_survives_a_runtime_restart(tmp_path):
    sentinel = FakeClient()
    c, _, _ = make_client(tmp_path, sentinel=sentinel)
    with c:
        sid = start(c)
        for qid, text in ANSWERS[:3]:
            assert typed(c, sid, qid, text).status_code == 200
    with restarted(tmp_path, sentinel) as c2:
        for qid, text in ANSWERS[3:]:
            assert typed(c2, sid, qid, text).status_code == 200
        assert c2.get(f"/checkin/sessions/{sid}/summary").json()["share"]["record"]["input_mode"] == "text"
        assert c2.post(f"/checkin/sessions/{sid}/approve", json={"severities": {}}).json()["status"] == "sent"
    assert sentinel.sent[0]["input_mode"] == "text"


def test_typed_words_are_never_logged(tmp_path, caplog, capfd):
    caplog.set_level(logging.DEBUG)
    secret = "Zorblat Quenwick 555-0177 itchy rash"
    c, _, _ = make_client(tmp_path)
    with c:
        sid = start(c)
        assert typed(c, sid, "q2", secret).status_code == 200
        assert typed(c, sid, "q1", "x" * 1001).status_code == 422
        assert typed(c, sid, "q1", "   ").status_code == 400
        c.get(f"/checkin/sessions/{sid}/summary")
    out, err = capfd.readouterr()
    for word in ("Zorblat", "Quenwick", "555-0177", "itchy"):
        assert word not in caplog.text and word not in out and word not in err
