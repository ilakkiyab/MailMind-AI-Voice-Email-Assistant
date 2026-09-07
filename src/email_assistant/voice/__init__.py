"""Local speech-to-text services."""

from __future__ import annotations

import io
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

TRANSCRIPTION_MODEL = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
SUPPORTED_AUDIO_SUFFIXES = {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".ogg", ".opus", ".wav", ".webm"}


class SpeechToTextError(Exception):
    """Base exception for user-facing speech-to-text failures."""


class NoAudioError(SpeechToTextError):
    """Raised when transcription is requested without recorded audio."""


class EmptyTranscriptionError(SpeechToTextError):
    """Raised when local Whisper returns no text."""


class InvalidAudioError(SpeechToTextError):
    """Raised when the recording is missing or cannot be decoded."""


class ModelLoadError(SpeechToTextError):
    """Raised when the local Whisper model cannot be loaded."""


class TranscriptionAPIError(SpeechToTextError):
    """Raised when local Whisper transcription fails."""


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    """Load and retain one CPU-optimized Whisper model per app process."""
    return WhisperModel(TRANSCRIPTION_MODEL, device=DEVICE, compute_type=COMPUTE_TYPE)


def _validate_audio(audio_data: bytes, filename: str, content_type: str) -> None:
    if not audio_data:
        raise NoAudioError("No audio was recorded.")
    suffix = Path(filename).suffix.lower()
    mime = (content_type or "").lower().split(";", 1)[0].strip()
    if suffix and suffix not in SUPPORTED_AUDIO_SUFFIXES and not mime.startswith("audio/"):
        raise InvalidAudioError(
            "The recording format is not supported. Please record again or upload a common audio file."
        )
    if suffix == ".wav" or mime in {"audio/wav", "audio/wave", "audio/x-wav"}:
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                if wav_file.getnframes() == 0 or wav_file.getframerate() <= 0:
                    raise InvalidAudioError("The WAV recording is empty or invalid. Please record it again.")
        except (EOFError, wave.Error) as exc:
            raise InvalidAudioError(
                "The WAV recording is invalid or incomplete. Please record it again."
            ) from exc


def _looks_like_invalid_audio(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "invaliddata" in name or any(
        marker in message
        for marker in ("invalid data", "could not open input", "error opening input", "failed to decode")
    )


def transcribe_audio(
    audio_data: bytes,
    *,
    filename: str = "voice_instruction.wav",
    content_type: str = "audio/wav",
    client: Any | None = None,
) -> str:
    """Transcribe recorded audio locally with CPU-optimized faster-whisper."""
    _validate_audio(audio_data, filename, content_type)
    try:
        model = client or _get_model()
    except Exception as exc:
        raise ModelLoadError(
            "The local Whisper model could not be loaded. Check the installation and available disk space, then try again."
        ) from exc

    audio_file = io.BytesIO(audio_data)
    audio_file.name = Path(filename).name or "voice_instruction.wav"
    try:
        segments, _ = model.transcribe(audio_file, language="en", beam_size=1, vad_filter=True)
        transcription = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    except Exception as exc:
        if _looks_like_invalid_audio(exc):
            raise InvalidAudioError(
                "Local Whisper could not decode this recording. Please record a new audio clip."
            ) from exc
        raise TranscriptionAPIError(
            "Local Whisper could not complete the transcription. Please try again."
        ) from exc

    if not transcription:
        raise EmptyTranscriptionError(
            "The recording was processed, but no speech could be transcribed."
        )
    return transcription
