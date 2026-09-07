"""Tests for the local faster-whisper speech-to-text service."""

import io
import wave
from types import SimpleNamespace

import pytest

from email_assistant import voice
from email_assistant.voice import (
    EmptyTranscriptionError,
    InvalidAudioError,
    ModelLoadError,
    NoAudioError,
    TranscriptionAPIError,
    transcribe_audio,
)


def wav_bytes(frames=1600):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


class FakeWhisperModel:
    def __init__(self, texts=None, error=None):
        self.texts = texts or []
        self.error = error
        self.request = None

    def transcribe(self, audio, **kwargs):
        self.request = (audio, kwargs)
        if self.error:
            raise self.error
        return (iter(SimpleNamespace(text=text) for text in self.texts), SimpleNamespace())


def test_transcribe_audio_returns_clean_text():
    model = FakeWhisperModel(["  Draft", " a reply.  "])
    assert transcribe_audio(wav_bytes(), client=model) == "Draft a reply."
    assert model.request[1] == {"language": "en", "beam_size": 1, "vad_filter": True}


def test_transcribe_audio_rejects_missing_audio():
    with pytest.raises(NoAudioError):
        transcribe_audio(b"")


def test_transcribe_audio_rejects_invalid_wav():
    with pytest.raises(InvalidAudioError):
        transcribe_audio(b"not wav")


def test_transcribe_audio_rejects_empty_wav():
    with pytest.raises(InvalidAudioError):
        transcribe_audio(wav_bytes(frames=0))


def test_transcribe_audio_rejects_empty_result():
    with pytest.raises(EmptyTranscriptionError):
        transcribe_audio(wav_bytes(), client=FakeWhisperModel(["  "]))


def test_transcribe_audio_reports_decode_failure():
    model = FakeWhisperModel(error=RuntimeError("Invalid data found when processing input"))
    with pytest.raises(InvalidAudioError):
        transcribe_audio(wav_bytes(), client=model)


def test_transcribe_audio_reports_transcription_failure():
    model = FakeWhisperModel(error=RuntimeError("inference failed"))
    with pytest.raises(TranscriptionAPIError):
        transcribe_audio(wav_bytes(), client=model)


def test_transcribe_audio_reports_model_load_failure(monkeypatch):
    def fail_to_load():
        raise RuntimeError("load failed")

    monkeypatch.setattr(voice, "_get_model", fail_to_load)
    with pytest.raises(ModelLoadError):
        transcribe_audio(wav_bytes())


def test_model_configuration_and_cache(monkeypatch):
    calls = []

    def fake_model(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    voice._get_model.cache_clear()
    monkeypatch.setattr(voice, "WhisperModel", fake_model)
    assert voice._get_model() is voice._get_model()
    assert calls == [(("base.en",), {"device": "cpu", "compute_type": "int8"})]
    voice._get_model.cache_clear()
