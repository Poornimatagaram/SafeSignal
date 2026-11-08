"""VC-07: "repeat" and "slower" voice commands (rule-based)."""

import pytest

from sentinel_patient.commands import COMMANDS, detect_command


def test_commands_tuple():
    assert COMMANDS == ("repeat", "slower")


@pytest.mark.parametrize("utterance", [
    "repeat", "Repeat.", "REPEAT!", "say that again", "Say it again please", "pardon, can you repeat that?",
    "again please", "Again?", "eh? say that again, dear", "Sorry, I didn't catch that", "come again?",
    "could you repeat the question please", "one more time please", "Pardon?", "what did you say?",
    "Can you say that again, love?",
])
def test_repeat(utterance):
    assert detect_command(utterance) == "repeat"


@pytest.mark.parametrize("utterance", [
    "slower", "Slower!", "slow down", "Slow down please.", "can you say it slower", "more slowly please",
    "please repeat that slower", "say that again, slowly", "too fast, sorry",
    "Could you speak more slowly, dear?", "SLOW IT DOWN",
])
def test_slower(utterance):
    assert detect_command(utterance) == "slower"


@pytest.mark.parametrize("utterance", [
    "it repeats every morning", "I've been slower walking", "the rash came back again",
    "I had to repeat my tablets", "my rash is bad again", "I feel slower than usual", "", "   ", "eh?", "please",
    "yes", "the diarrhea keeps coming back again and again",
    "say that again " + "and again " * 10,  # too long to be only a command
])
def test_not_a_command(utterance):
    assert detect_command(utterance) is None


def test_none_input():
    assert detect_command(None) is None  # type: ignore[arg-type]
