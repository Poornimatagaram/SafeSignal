"""Speech-to-text on the device only (VC-02, VC-03, PV-03).

faster-whisper runs on the CPU with a model from the local Hugging Face cache (`local_files_only=True`). The
audio arrives as bytes (patient-web -> main.py on localhost) and is decoded in memory with PyAV: it is never
written to disk, nothing here keeps a reference to it after `transcribe` returns, and no network call is made.
Nothing in this module logs or prints a transcript, and error messages never contain one.

One-time setup, the only step that uses the network (it fetches the public model and nothing else):
    uv run python -m sentinel_patient.stt --download
Check that the model loads offline:
    uv run python -m sentinel_patient.stt

`faster_whisper`, `av` and `numpy` are imported inside functions so `import sentinel_patient.stt` stays cheap.
"""

from __future__ import annotations

import argparse
import io
import itertools
import os
import sys
import threading
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import numpy as np

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 300  # one answer; also caps memory for highly compressed input (5 min = 19 MB of samples)
SAMPLE_RATE = 16_000  # what Whisper expects
MIN_SAMPLES = SAMPLE_RATE // 10  # under 0.1 s there is nothing to transcribe

DEFAULT_MODEL = "base.en"
MODEL_ENV = "PATIENT_WHISPER_MODEL"
DOWNLOAD_HINT = "run `uv run python -m sentinel_patient.stt --download`"

# Containers that browsers record into (Chrome/Edge webm-opus, Firefox ogg-opus or webm, Safari mp4-aac) and plain
# audio files. FFmpeg probes only these demuxers, so playlist-style input (hls, concat) can never make it open a
# URL or a local file. Names match FFmpeg demuxer names ("mov" covers mp4/m4a, "matroska" covers webm).
CONTAINER_WHITELIST = "matroska,webm,ogg,mov,mp4,wav,mp3,flac,aac"

# Decoding settings (VC-03: a long pause inside an answer must not lose the words after it).
# - vad_filter: Silero VAD drops non-speech before decoding. Silence or room noise alone gives "" instead of a
#   Whisper hallucination (without VAD, 3 s of silence came back as "You"). faster-whisper keeps every speech
#   chunk and joins them; it has no end-of-utterance cut-off, so nothing after a pause is discarded here.
# - min_silence_duration_ms=1000: a pause longer than 1 s is cut out and the speech on both sides is joined with
#   speech_pad_ms of padding each side (~0.8 s gap), so the decoder never has to cross a long silence mid-answer.
# - condition_on_previous_text=False: no repetition loops carried from one 30 s window into the next.
# - language="en": the models are English-only (*.en); skips language detection.
# Deciding when the answer has ended (stop recording) is the recorder's job in patient-web, not this module's.
DECODE_OPTIONS: dict[str, Any] = {
    "language": "en",
    "beam_size": 5,
    "condition_on_previous_text": False,
    "vad_filter": True,
    "vad_parameters": {"min_silence_duration_ms": 1000, "speech_pad_ms": 400},
}


class TranscriptionError(Exception):
    """The audio could not be decoded or transcribed. The message never contains transcript text."""


class ModelUnavailable(TranscriptionError):
    """The Whisper model is not in the local cache (or could not be loaded from it)."""


class Transcriber(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


def _decode(audio: bytes) -> np.ndarray:
    """Decode any whitelisted container to 16 kHz mono float32 samples, entirely in memory."""
    import av
    import numpy as np

    max_bytes = MAX_AUDIO_SECONDS * SAMPLE_RATE * 2  # s16 mono
    pcm = bytearray()
    try:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        with io.BytesIO(audio) as buf, av.open(
            buf, mode="r", container_options={"format_whitelist": CONTAINER_WHITELIST}
        ) as container:
            if not container.streams.audio:
                raise TranscriptionError("the upload has no audio track")
            for frame in itertools.chain(_frames(container, container.streams.audio[0]), [None]):  # None flushes
                if frame is not None:
                    frame.pts = None  # browser recordings can carry uneven timestamps; order is enough
                for out in resampler.resample(frame):
                    pcm += out.to_ndarray().tobytes()
                if len(pcm) > max_bytes:
                    raise TranscriptionError(f"audio is longer than {MAX_AUDIO_SECONDS} seconds")
    except TranscriptionError:
        raise
    except Exception as exc:  # PyAV/FFmpeg errors carry no audio content, only codes
        raise TranscriptionError(f"could not decode the audio ({type(exc).__name__})") from exc
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0  # astype copies out of pcm
    del pcm
    return samples


def _frames(container, stream):
    """Decode packet by packet: a packet the decoder rejects is skipped (it costs a few milliseconds, not the rest
    of the answer), and a container that ends early (a recording cut off mid-write) keeps what came before."""
    import av

    packets = container.demux(stream)
    while True:
        try:
            packet = next(packets)
        except (StopIteration, av.error.InvalidDataError):
            return
        try:
            yield from packet.decode()
        except av.error.InvalidDataError:
            continue


class WhisperTranscriber:
    """faster-whisper from the local cache only. The model loads on the first `transcribe` call."""

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu", compute_type: str = "int8"):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    try:
                        self._model = WhisperModel(self.model_name, device=self.device,
                                                   compute_type=self.compute_type, local_files_only=True)
                    except Exception as exc:  # not cached (LocalEntryNotFoundError), bad name, damaged files
                        raise ModelUnavailable(
                            f"Whisper model {self.model_name!r} could not be loaded from the local cache "
                            f"({type(exc).__name__}); {DOWNLOAD_HINT}") from exc
        return self._model

    def transcribe(self, audio: bytes) -> str:
        """Return the transcript ("" for empty, silent or noise-only audio).

        Raises TranscriptionError for undecodable or oversized audio, ModelUnavailable if the model is missing.
        """
        if not audio:
            return ""
        if len(audio) > MAX_AUDIO_BYTES:
            raise TranscriptionError(f"audio is larger than {MAX_AUDIO_BYTES} bytes")
        samples = _decode(audio)
        if samples.size < MIN_SAMPLES:
            return ""
        model = self._load()
        try:
            segments, _info = model.transcribe(samples, **DECODE_OPTIONS)
            parts = [segment.text.strip() for segment in segments]  # decoding runs while iterating
        except Exception as exc:
            raise TranscriptionError(f"transcription failed ({type(exc).__name__})") from exc
        finally:
            del samples
        return " ".join(" ".join(parts).split())


_transcribers: dict[str, WhisperTranscriber] = {}
_transcribers_lock = threading.Lock()


def _model_name_from_env() -> str:
    return os.environ.get(MODEL_ENV, "").strip() or DEFAULT_MODEL


def get_transcriber() -> Transcriber:
    """The process-wide transcriber for the model named by PATIENT_WHISPER_MODEL (default base.en)."""
    name = _model_name_from_env()
    with _transcribers_lock:
        if name not in _transcribers:
            _transcribers[name] = WhisperTranscriber(name)
        return _transcribers[name]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sentinel_patient.stt",
                                     description="Fetch the public Whisper model once, then check it loads offline.")
    parser.add_argument("--download", action="store_true",
                        help="download the model into the local Hugging Face cache (the only network use)")
    parser.add_argument("--model", help=f"model name (default: ${MODEL_ENV} or {DEFAULT_MODEL})")
    args = parser.parse_args(argv)
    name = args.model or _model_name_from_env()
    if args.download:
        from faster_whisper import download_model

        print(f"Whisper model {name} saved to {download_model(name)}")
    try:
        WhisperTranscriber(name)._load()
    except ModelUnavailable as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Whisper model {name} loads offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
