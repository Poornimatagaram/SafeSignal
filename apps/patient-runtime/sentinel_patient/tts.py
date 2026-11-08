"""Spoken questions and summaries, offline only (VC-01, VC-07, VC-08). Never uses online voices.

Engines (both run locally as a subprocess with an argument list, never a shell):
- `say`: macOS system voices, offline. Optional voice from PATIENT_TTS_VOICE (`say -v '?'` lists them).
- `piper`: the Piper CLI with a local voice model, PATIENT_PIPER_MODEL = path to the `.onnx` file (its `.onnx.json`
  sits next to it). The model must be an existing file, so Piper never tries to download a voice.
  PATIENT_PIPER_BIN overrides the `piper` command.
PATIENT_TTS_ENGINE = "say" | "piper" picks one; by default `say` if present, else Piper if configured.

`synthesize` returns a complete WAV file (RIFF, 16-bit PCM, mono). `slow=True` is the "slower" command (VC-07).
The text goes to the engine on stdin, never on the command line, and is never logged or printed. The engine
writes to a temporary file that is deleted in `finally`.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

Runner = Callable[..., subprocess.CompletedProcess]
TIMEOUT_SECONDS = 60
EMPTY_WAV_RATE = 22_050


class TTSUnavailable(RuntimeError):
    """No offline voice is configured, or the engine failed. The message never contains the text."""


class Speaker(Protocol):
    def synthesize(self, text: str, *, slow: bool = False) -> bytes: ...  # complete WAV file, 16-bit PCM mono


def _find_say() -> str | None:
    return shutil.which("say") if sys.platform == "darwin" else None


def _find_piper() -> str | None:
    return shutil.which(os.environ.get("PATIENT_PIPER_BIN", "").strip() or "piper")


def _empty_wav(rate: int = EMPTY_WAV_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
    return buf.getvalue()


def _check_wav(data: bytes, engine: str) -> bytes:
    try:
        with wave.open(io.BytesIO(data)) as w:
            ok = w.getnchannels() == 1 and w.getsampwidth() == 2
    except (wave.Error, EOFError) as exc:
        raise TTSUnavailable(f"{engine} did not produce a WAV file") from exc
    if not ok:
        raise TTSUnavailable(f"{engine} did not produce 16-bit mono WAV")
    return data


def _synthesize(engine: str, command: Callable[[str], list[str]], text: str, runner: Runner) -> bytes:
    """Run `command(output_path)` with the text on stdin and return the WAV it wrote."""
    if not text.strip():
        return _empty_wav()
    fd, path = tempfile.mkstemp(prefix="sentinel-tts-", suffix=".wav")
    os.close(fd)
    try:
        try:
            result = runner(command(path), input=text.encode("utf-8"), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TTSUnavailable(f"{engine} could not run ({type(exc).__name__})") from exc
        if result.returncode != 0:
            raise TTSUnavailable(f"{engine} exited with code {result.returncode}")
        data = Path(path).read_bytes()
    finally:
        Path(path).unlink(missing_ok=True)
    return _check_wav(data, engine)


class SaySpeaker:
    """macOS `say` with an offline system voice. Speaking rate is in words per minute."""

    rate_wpm = 170
    # "slower" (VC-07). Current macOS voices map the rate to speed in coarse steps with a floor: on this project's
    # Mac, 115 wpm was only 1.1x longer than 170, while 60 wpm was 1.3x longer for Samantha, Daniel and Fred and
    # still transcribed word for word.
    slow_rate_wpm = 60
    sample_rate = 22_050

    def __init__(self, voice: str | None = None, *, binary: str | None = None, runner: Runner = subprocess.run):
        self.voice = voice or os.environ.get("PATIENT_TTS_VOICE", "").strip() or None
        self.binary = binary or _find_say()
        if not self.binary:
            raise TTSUnavailable("macOS `say` is not available on this machine")
        self._runner = runner

    def command(self, output_path: str, *, slow: bool = False) -> list[str]:
        cmd = [self.binary, "-o", output_path, "--file-format=WAVE", f"--data-format=LEI16@{self.sample_rate}",
               "-r", str(self.slow_rate_wpm if slow else self.rate_wpm)]
        if self.voice:
            cmd += ["-v", self.voice]
        return cmd + ["-f", "-"]  # read the text from stdin

    def synthesize(self, text: str, *, slow: bool = False) -> bytes:
        return _synthesize("say", lambda path: self.command(path, slow=slow), text, self._runner)


class PiperSpeaker:
    """The Piper CLI with a local `.onnx` voice. A larger length_scale speaks more slowly."""

    length_scale = 1.0
    slow_length_scale = 1.5  # "slower" (VC-07)

    def __init__(self, model_path: str | os.PathLike[str] | None = None, *, binary: str | None = None,
                 runner: Runner = subprocess.run):
        model = str(model_path or os.environ.get("PATIENT_PIPER_MODEL", "").strip())
        if not model:
            raise TTSUnavailable("set PATIENT_PIPER_MODEL to a local Piper voice (.onnx)")
        if not Path(model).is_file():
            raise TTSUnavailable("PATIENT_PIPER_MODEL does not point to an existing .onnx file")
        self.model_path = model
        self.binary = binary or _find_piper()
        if not self.binary:
            raise TTSUnavailable("the `piper` command is not installed (or set PATIENT_PIPER_BIN)")
        self._runner = runner

    def command(self, output_path: str, *, slow: bool = False) -> list[str]:
        return [self.binary, "--model", self.model_path, "--output_file", output_path,
                "--length_scale", str(self.slow_length_scale if slow else self.length_scale)]

    def synthesize(self, text: str, *, slow: bool = False) -> bytes:
        return _synthesize("piper", lambda path: self.command(path, slow=slow), text, self._runner)


def get_speaker() -> Speaker:
    """PATIENT_TTS_ENGINE picks the engine; by default `say` if present, else Piper if configured."""
    engine = os.environ.get("PATIENT_TTS_ENGINE", "").strip().lower()
    if engine == "say":
        return SaySpeaker()
    if engine == "piper":
        return PiperSpeaker()
    if engine:
        raise TTSUnavailable(f"PATIENT_TTS_ENGINE must be 'say' or 'piper', not {engine!r}")
    if _find_say():
        return SaySpeaker()
    try:
        return PiperSpeaker()
    except TTSUnavailable as exc:
        raise TTSUnavailable(f"no offline voice: macOS `say` is missing and Piper is not configured ({exc})") from exc
