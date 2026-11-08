"""Task A2 voice: local speech-to-text (VC-02, VC-03, PV-03) and offline text-to-speech (VC-01, VC-07).

All speech is synthetic, generated at test time with macOS `say` into pytest's tmp_path (never committed).
Tests that need `say`, ffmpeg or the cached Whisper model skip when those are missing.
"""

import builtins
import io
import os
import random
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import pytest

from sentinel_patient import stt, tts
from sentinel_patient.stt import (MAX_AUDIO_BYTES, ModelUnavailable, TranscriptionError, WhisperTranscriber,
                                  get_transcriber)
from sentinel_patient.tts import PiperSpeaker, SaySpeaker, TTSUnavailable, get_speaker

APP_DIR = Path(__file__).resolve().parents[1]
RATE = 16_000

SAY = shutil.which("say") if sys.platform == "darwin" else None
FFMPEG = shutil.which("ffmpeg") or next(
    (p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if os.path.exists(p)), None)


def _model_cached(name: str = "base.en") -> bool:
    try:
        from faster_whisper import download_model

        download_model(name, local_files_only=True)
        return True
    except Exception:
        return False


needs_say = pytest.mark.skipif(SAY is None, reason="macOS `say` not available")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")
needs_model = pytest.mark.skipif(not _model_cached(), reason="Whisper base.en not cached; run "
                                 "`uv run python -m sentinel_patient.stt --download`")

PHRASE_A = "I have a rash on my arms"
PHRASE_B = "and my nails are sore"


# ---------- synthetic audio helpers ----------

def wav_bytes(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(RATE * seconds)


def room_noise(seconds: float, amplitude: int = 60, seed: int = 1) -> bytes:
    """Quiet hiss (about -55 dBFS), like a real microphone between words."""
    rng = random.Random(seed)
    n = int(RATE * seconds)
    return struct.pack(f"<{n}h", *(int(rng.gauss(0, amplitude)) for _ in range(n)))


def softer(pcm: bytes, gain: float) -> bytes:
    n = len(pcm) // 2
    return struct.pack(f"<{n}h", *(int(s * gain) for s in struct.unpack(f"<{n}h", pcm)))


def say_pcm(text: str, directory: Path, name: str) -> bytes:
    path = directory / f"{name}.wav"
    subprocess.run([SAY, "-o", str(path), "--file-format=WAVE", f"--data-format=LEI16@{RATE}", text], check=True)
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE)
        return w.readframes(w.getnframes())


def words(text: str) -> set[str]:
    return set("".join(c if c.isalnum() else " " for c in text.lower()).split())


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    if SAY is None:
        pytest.skip("macOS `say` not available")
    d = tmp_path_factory.mktemp("speech")
    return {"a": say_pcm(PHRASE_A, d, "a"), "b": say_pcm(PHRASE_B, d, "b"), "dir": d}


@pytest.fixture(scope="module")
def transcriber():
    return WhisperTranscriber("base.en")


@pytest.fixture()
def offline(monkeypatch):
    """Refuse and record any Python-level network attempt; the test fails at teardown if there was one
    (recorded, because the code under test may wrap the refusal in its own exception)."""
    attempts = []

    def refuse(name):
        def _refuse(*args, **kwargs):
            attempts.append(name)
            raise OSError("network disabled in this test")
        return _refuse

    monkeypatch.setattr(socket.socket, "connect", refuse("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", refuse("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", refuse("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", refuse("getaddrinfo"))
    yield
    assert attempts == [], "network access attempted"


# ---------- speech-to-text: no model needed ----------

def test_importing_voice_modules_does_not_load_whisper():
    code = ("import sys, sentinel_patient.stt, sentinel_patient.tts; "
            "heavy = {'faster_whisper', 'av', 'numpy', 'ctranslate2', 'onnxruntime'} & set(sys.modules); "
            "assert not heavy, heavy")
    subprocess.run([sys.executable, "-c", code], cwd=APP_DIR, check=True)


def test_empty_upload_returns_empty_text_without_loading_a_model():
    assert WhisperTranscriber("Systran/faster-whisper-not-cached").transcribe(b"") == ""


def test_oversized_upload_is_refused_before_decoding():
    with pytest.raises(TranscriptionError, match="larger than"):
        WhisperTranscriber().transcribe(bytes(MAX_AUDIO_BYTES + 1))


@pytest.mark.parametrize("garbage", [
    b"this is not audio " * 64,
    random.Random(7).randbytes(8192),
    b"RIFF\x00\x00\x00\x00WAVE",  # truncated header
    b"#EXTM3U\n#EXTINF:10,\nhttp://127.0.0.1:9/segment.ts\n#EXT-X-ENDLIST\n",  # playlist, not audio
], ids=["text", "random", "truncated-wav", "playlist"])
def test_undecodable_bytes_raise_transcription_error(garbage):
    with pytest.raises(TranscriptionError, match="could not decode") as err:
        WhisperTranscriber().transcribe(garbage)
    assert not isinstance(err.value, ModelUnavailable)


@needs_say
def test_containers_outside_the_whitelist_are_refused(tmp_path):
    aiff = tmp_path / "clip.aiff"  # valid audio, but no browser records AIFF
    subprocess.run([SAY, "-o", str(aiff), "one two three"], check=True)
    with pytest.raises(TranscriptionError, match="could not decode"):
        WhisperTranscriber().transcribe(aiff.read_bytes())


def test_missing_model_raises_model_unavailable_without_network(offline):
    with pytest.raises(ModelUnavailable, match=r"python -m sentinel_patient\.stt --download"):
        WhisperTranscriber("Systran/faster-whisper-not-cached").transcribe(wav_bytes(room_noise(1.0)))
    assert issubclass(ModelUnavailable, TranscriptionError)


def test_get_transcriber_is_cached_per_process_and_reads_the_model_env(monkeypatch):
    monkeypatch.delenv("PATIENT_WHISPER_MODEL", raising=False)
    default = get_transcriber()
    assert default.model_name == "base.en" and get_transcriber() is default
    assert (default.device, default.compute_type) == ("cpu", "int8")
    monkeypatch.setenv("PATIENT_WHISPER_MODEL", "tiny.en")
    assert get_transcriber().model_name == "tiny.en" and get_transcriber() is get_transcriber()


# ---------- speech-to-text with the cached model ----------

@needs_model
@pytest.mark.parametrize("gap", ["silence", "room-noise-then-softer-voice"])
def test_three_second_pause_keeps_the_words_after_it(clips, transcriber, gap):  # VC-03
    if gap == "silence":
        pcm = clips["a"] + silence(3.0) + clips["b"]
    else:
        pcm = clips["a"] + room_noise(3.0) + softer(clips["b"], 0.25)
    heard = words(transcriber.transcribe(wav_bytes(pcm)))
    assert {"rash", "arms"} <= heard, "words before the pause"
    assert {"nails", "sore"} <= heard, "words after the pause"


@needs_model
@needs_ffmpeg
@pytest.mark.parametrize("ext, codec", [("webm", "libopus"), ("ogg", "libopus"), ("m4a", "aac")],
                         ids=["chrome-webm-opus", "firefox-ogg-opus", "safari-mp4-aac"])
def test_browser_recording_formats_are_transcribed(clips, transcriber, tmp_path, ext, codec):
    src = tmp_path / "answer.wav"
    src.write_bytes(wav_bytes(clips["a"] + silence(1.0) + clips["b"]))
    out = tmp_path / f"answer.{ext}"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(src), "-c:a", codec, "-b:a", "32k",
                    str(out)], check=True)
    heard = words(transcriber.transcribe(out.read_bytes()))
    assert {"rash", "arms", "nails", "sore"} <= heard


@needs_model
@needs_ffmpeg
def test_recording_cut_off_mid_write_keeps_what_was_said_before_the_cut(clips, transcriber, tmp_path):
    src = tmp_path / "answer.wav"
    src.write_bytes(wav_bytes(clips["a"] + silence(1.0) + clips["b"]))
    out = tmp_path / "answer.webm"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(src), "-c:a", "libopus", str(out)],
                   check=True)
    data = out.read_bytes()
    assert {"rash", "arms"} <= words(transcriber.transcribe(data[: len(data) * 6 // 10]))


@needs_model
@pytest.mark.parametrize("audio", [silence(3.0), room_noise(3.0), silence(0.05)], ids=["silence", "noise", "tiny"])
def test_silent_audio_returns_empty_text(transcriber, audio):
    assert transcriber.transcribe(wav_bytes(audio)) == ""


@needs_model
def test_transcription_is_offline_and_writes_nothing_to_disk(clips, monkeypatch, offline):  # VC-02, PV-03
    audio = wav_bytes(clips["a"])
    real_open, real_os_open, real_mkstemp = builtins.open, os.open, tempfile.mkstemp
    writes = []

    def read_only_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    def read_only_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            writes.append(str(path))
        return real_os_open(path, flags, *args, **kwargs)

    def no_mkstemp(*args, **kwargs):
        writes.append("mkstemp")
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_open)
    monkeypatch.setattr(os, "open", read_only_os_open)
    monkeypatch.setattr(tempfile, "mkstemp", no_mkstemp)
    fresh = WhisperTranscriber("base.en")  # the model also loads under these restrictions
    assert {"rash", "arms"} <= words(fresh.transcribe(audio))
    assert writes == [], "something was written to disk during transcription"


@needs_model
def test_transcript_is_never_logged_or_printed(clips, transcriber, caplog, capfd):
    import logging

    caplog.set_level(logging.DEBUG)
    text = transcriber.transcribe(wav_bytes(clips["a"]))
    assert "rash" in text.lower()
    out, err = capfd.readouterr()
    for channel in (caplog.text, out, err):
        assert "rash" not in channel.lower() and "arms" not in channel.lower()


@needs_model
def test_setup_check_reports_the_model_loads_offline(offline, capsys):
    assert stt.main(["--model", "base.en"]) == 0
    assert "loads offline" in capsys.readouterr().out
    assert stt.main(["--model", "Systran/faster-whisper-not-cached"]) == 1
    assert "--download" in capsys.readouterr().err


# ---------- text-to-speech ----------

QUESTION = "Have you had any rash or itching since your last check-in?"


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2)
        assert w.getnframes() > 0
        return w.getnframes() / w.getframerate()


@needs_say
def test_say_returns_mono_16_bit_wav_and_slow_is_slower(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    speaker = SaySpeaker()
    normal = speaker.synthesize(QUESTION)
    slow = speaker.synthesize(QUESTION, slow=True)
    assert normal.startswith(b"RIFF") and slow.startswith(b"RIFF")
    assert wav_seconds(slow) > 1.2 * wav_seconds(normal)
    assert list(tmp_path.iterdir()) == [], "temporary WAV left behind"


def fake_wav() -> bytes:
    return wav_bytes(silence(0.5), rate=22_050)


class FakeRunner:
    """Stands in for subprocess.run: records the call and writes a WAV to the engine's output path."""

    def __init__(self, returncode: int = 0, output_flag: str = "--output_file"):
        self.calls = []
        self.returncode = returncode
        self.output_flag = output_flag

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        out = Path(cmd[cmd.index(self.output_flag) + 1])
        assert out.exists(), "the temporary output file exists while the engine runs"
        if self.returncode == 0:
            out.write_bytes(fake_wav())
        return subprocess.CompletedProcess(cmd, self.returncode)


@pytest.fixture()
def piper_model(tmp_path):
    model = tmp_path / "en_US-voice.onnx"
    model.write_bytes(b"synthetic placeholder")
    return model


def test_piper_command_and_stdin(piper_model, tmp_path, monkeypatch):
    out_dir = tmp_path / "tmp"
    out_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(out_dir))
    runner = FakeRunner()
    speaker = PiperSpeaker(piper_model, binary="/opt/piper/piper", runner=runner)
    assert speaker.synthesize(QUESTION) == fake_wav()
    assert speaker.synthesize(QUESTION, slow=True) == fake_wav()
    (normal, kw), (slow, _) = runner.calls
    out = normal[normal.index("--output_file") + 1]
    assert normal == ["/opt/piper/piper", "--model", str(piper_model), "--output_file", out, "--length_scale", "1.0"]
    assert slow[-2:] == ["--length_scale", "1.5"]
    assert kw["input"] == QUESTION.encode() and kw.get("shell") is not True
    assert all(QUESTION not in arg for arg in normal + slow), "text must go on stdin, not the command line"
    assert list(out_dir.iterdir()) == [], "temporary WAV left behind"


def test_say_command_uses_voice_and_lower_rate_when_slow(monkeypatch):
    monkeypatch.setenv("PATIENT_TTS_VOICE", "Samantha")
    runner = FakeRunner(output_flag="-o")
    speaker = SaySpeaker(binary="/usr/bin/say", runner=runner)
    speaker.synthesize(QUESTION)
    speaker.synthesize(QUESTION, slow=True)
    (normal, kw), (slow, _) = runner.calls
    out = normal[normal.index("-o") + 1]
    assert normal == ["/usr/bin/say", "-o", out, "--file-format=WAVE", "--data-format=LEI16@22050", "-r", "170",
                      "-v", "Samantha", "-f", "-"]
    assert int(slow[slow.index("-r") + 1]) < int(normal[normal.index("-r") + 1])
    assert kw["input"] == QUESTION.encode()


def test_engine_failure_raises_and_cleans_up(piper_model, tmp_path, monkeypatch):
    out_dir = tmp_path / "tmp"
    out_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(out_dir))
    speaker = PiperSpeaker(piper_model, binary="piper", runner=FakeRunner(returncode=1))
    with pytest.raises(TTSUnavailable, match="exited with code 1") as err:
        speaker.synthesize(QUESTION)
    assert QUESTION not in str(err.value)
    assert list(out_dir.iterdir()) == []


def test_engine_output_that_is_not_mono_wav_is_refused(piper_model):
    def stereo_runner(cmd, **kwargs):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(22_050)
            w.writeframes(b"\x00" * 400)
        Path(cmd[cmd.index("--output_file") + 1]).write_bytes(buf.getvalue())
        return subprocess.CompletedProcess(cmd, 0)

    with pytest.raises(TTSUnavailable, match="16-bit mono"):
        PiperSpeaker(piper_model, binary="piper", runner=stereo_runner).synthesize(QUESTION)


def test_empty_text_gives_an_empty_wav_without_running_the_engine(piper_model):
    runner = FakeRunner()
    data = PiperSpeaker(piper_model, binary="piper", runner=runner).synthesize("   ")
    assert data.startswith(b"RIFF") and runner.calls == []
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getnframes()) == (1, 2, 0)


# get_speaker selection by environment

@pytest.fixture()
def voices(monkeypatch, piper_model):
    """Control which engines look installed; returns a setter."""
    for var in ("PATIENT_TTS_ENGINE", "PATIENT_PIPER_MODEL", "PATIENT_PIPER_BIN", "PATIENT_TTS_VOICE"):
        monkeypatch.delenv(var, raising=False)

    def set_available(say: bool, piper: bool, model: bool):
        monkeypatch.setattr(tts, "_find_say", lambda: "/usr/bin/say" if say else None)
        monkeypatch.setattr(tts, "_find_piper", lambda: "/usr/local/bin/piper" if piper else None)
        if model:
            monkeypatch.setenv("PATIENT_PIPER_MODEL", str(piper_model))

    return set_available


@pytest.mark.parametrize("engine, say, piper, model, expected", [
    (None, True, True, True, SaySpeaker),       # default prefers say
    (None, False, True, True, PiperSpeaker),    # falls back to configured Piper
    ("say", True, True, True, SaySpeaker),
    ("piper", True, True, True, PiperSpeaker),  # explicit choice wins over the default
    (" Piper ", True, True, True, PiperSpeaker),
])
def test_get_speaker_selects_by_env(voices, monkeypatch, engine, say, piper, model, expected):
    voices(say, piper, model)
    if engine is not None:
        monkeypatch.setenv("PATIENT_TTS_ENGINE", engine)
    assert isinstance(get_speaker(), expected)


@pytest.mark.parametrize("engine, say, piper, model", [
    (None, False, True, False),     # no say, Piper has no model
    (None, False, False, True),     # no say, piper binary missing
    ("say", False, True, True),     # say requested but missing
    ("piper", True, True, False),   # piper requested without a model
    ("cloud", True, True, True),    # unknown engine
])
def test_get_speaker_raises_when_no_offline_voice(voices, monkeypatch, engine, say, piper, model):
    voices(say, piper, model)
    if engine is not None:
        monkeypatch.setenv("PATIENT_TTS_ENGINE", engine)
    with pytest.raises(TTSUnavailable):
        get_speaker()


def test_piper_model_must_be_an_existing_file(voices, monkeypatch, tmp_path):
    voices(False, True, False)
    monkeypatch.setenv("PATIENT_PIPER_MODEL", str(tmp_path / "missing.onnx"))
    with pytest.raises(TTSUnavailable, match="existing .onnx"):
        PiperSpeaker()
