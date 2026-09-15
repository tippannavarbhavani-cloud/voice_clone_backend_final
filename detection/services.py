"""
Voice clone / deepfake detection service.

Pipeline for every clip: load -> (optional) noise reduction / voice
isolation -> run pretrained classifier -> compute a 0-100 risk score
-> band it into Genuine / Suspicious / High Risk -> attach
human-readable risk factors explaining *why*.

The classifier is a pretrained HuggingFace `audio-classification`
model fine-tuned to distinguish authentic speech from AI-generated /
cloned / spoofed speech. It's loaded lazily and cached as a
process-wide singleton. Swap it anytime via DETECTION_MODEL_NAME in
.env — no code changes needed as long as the replacement is
pipeline-compatible.
"""
import logging
import time

import librosa
import numpy as np
from django.conf import settings

logger = logging.getLogger("detection")

SYNTHETIC_LABELS = {"spoof", "fake", "synthetic", "cloned", "ai", "generated", "deepfake"}
AUTHENTIC_LABELS = {"bonafide", "real", "genuine", "authentic", "human"}

TARGET_SAMPLE_RATE = 16000
MIN_DURATION_SECONDS = 0.5
MAX_DURATION_SECONDS = 60  # trim very long uploads to keep inference fast

DEFAULT_THRESHOLDS = (0.35, 0.65)  # (suspicious_from, high_risk_from)


class DetectionServiceError(Exception):
    """Raised when audio can't be loaded or the model can't run."""


class _ModelSingleton:
    """Lazily loads the HF pipeline once per process."""

    _pipeline = None
    _model_name = None

    @classmethod
    def get(cls):
        model_name = settings.DETECTION_MODEL_NAME
        if cls._pipeline is None or cls._model_name != model_name:
            logger.info("Loading voice-clone detection model: %s", model_name)
            from transformers import pipeline  # imported lazily: heavy dependency

            cls._pipeline = pipeline(
                task="audio-classification",
                model=model_name,
                device=0 if settings.DETECTION_DEVICE == "cuda" else -1,
            )
            cls._model_name = model_name
        return cls._pipeline


def _load_audio(file_path: str):
    """Load and resample audio to what the model expects; return (array, duration)."""
    try:
        audio_array, sr = librosa.load(file_path, sr=TARGET_SAMPLE_RATE, mono=True)
    except Exception as exc:
        raise DetectionServiceError(f"Could not decode audio file: {exc}") from exc

    duration = len(audio_array) / TARGET_SAMPLE_RATE
    if duration < MIN_DURATION_SECONDS:
        raise DetectionServiceError(
            f"Audio is too short ({duration:.2f}s). Minimum is {MIN_DURATION_SECONDS}s."
        )

    max_samples = MAX_DURATION_SECONDS * TARGET_SAMPLE_RATE
    if len(audio_array) > max_samples:
        audio_array = audio_array[:max_samples]

    return audio_array, duration


def _isolate_voice(audio_array: np.ndarray) -> tuple[np.ndarray, bool]:
    """
    Background-noise reduction ("voice isolation") applied before
    analysis. Uses spectral-gating noise reduction; falls back to the
    original audio (and reports noise_reduction_applied=False) if the
    library is unavailable or errors on a particular clip, rather than
    failing the whole request over a best-effort cleanup step.
    """
    try:
        import noisereduce as nr

        cleaned = nr.reduce_noise(y=audio_array, sr=TARGET_SAMPLE_RATE, stationary=False)
        return cleaned, True
    except Exception as exc:
        logger.warning("Noise reduction skipped (falling back to raw audio): %s", exc)
        return audio_array, False


def _normalize_scores(raw_scores: list[dict]) -> tuple[float, dict]:
    """
    Map arbitrary model label names onto a single cloned_probability in [0, 1].
    `raw_scores` looks like: [{"label": "spoof", "score": 0.87}, {"label": "bonafide", "score": 0.13}]
    """
    cloned_score = None
    authentic_score = None

    for entry in raw_scores:
        label = str(entry.get("label", "")).lower()
        score = float(entry.get("score", 0.0))
        if label in SYNTHETIC_LABELS:
            cloned_score = score
        elif label in AUTHENTIC_LABELS:
            authentic_score = score

    if cloned_score is not None:
        return cloned_score, {"matched_label": "synthetic"}
    if authentic_score is not None:
        return 1.0 - authentic_score, {"matched_label": "authentic"}

    if raw_scores:
        return float(raw_scores[0].get("score", 0.5)), {"matched_label": "unmapped_fallback"}

    return 0.5, {"matched_label": "no_output"}


def _compute_risk_factors(audio_array: np.ndarray, duration: float, cloned_probability: float) -> list[str]:
    """
    Human-readable, heuristic signals shown alongside the score to explain
    *why* a clip was flagged. These are explainability aids based on
    simple acoustic features, not independently validated forensic
    claims — they're meant to give a reviewer useful context, not serve
    as courtroom-grade evidence.
    """
    factors = []

    if cloned_probability >= DEFAULT_THRESHOLDS[1]:
        factors.append("Acoustic classifier strongly matched patterns typical of synthetic speech.")
    elif cloned_probability >= DEFAULT_THRESHOLDS[0]:
        factors.append("Acoustic classifier found some patterns consistent with synthetic speech.")

    try:
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=audio_array)))
        if flatness > 0.35:
            factors.append("Unusually flat spectral profile — a trait sometimes seen in synthesized audio.")
    except Exception:
        pass

    try:
        rms = librosa.feature.rms(y=audio_array)[0]
        if len(rms) > 1 and np.std(rms) < 0.01:
            factors.append("Abnormally consistent energy/volume across the clip.")
    except Exception:
        pass

    try:
        f0, voiced_flag, _ = librosa.pyin(
            audio_array, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7")
        )
        voiced_f0 = f0[~np.isnan(f0)]
        if len(voiced_f0) > 10 and np.std(voiced_f0) < 5:
            factors.append("Unusually consistent pitch — natural speech typically has more variation.")
    except Exception:
        pass

    if duration < 2.0:
        factors.append("Very short clip — confidence is lower with less audio to analyze.")

    if not factors:
        factors.append("No strong risk indicators detected in this clip.")

    return factors


def _band_risk(cloned_probability: float, thresholds: tuple[float, float]) -> str:
    from .models import DetectionResult

    suspicious_from, high_risk_from = thresholds
    if cloned_probability >= high_risk_from:
        return DetectionResult.RiskLevel.HIGH_RISK
    elif cloned_probability >= suspicious_from:
        return DetectionResult.RiskLevel.SUSPICIOUS
    return DetectionResult.RiskLevel.GENUINE


def analyze_audio_file(
    file_path: str,
    thresholds: tuple[float, float] = DEFAULT_THRESHOLDS,
    apply_noise_reduction: bool = True,
) -> dict:
    """
    Run the full detection pipeline on a file already saved to disk.
    Raises DetectionServiceError on failure.
    """
    start = time.monotonic()

    audio_array, duration = _load_audio(file_path)

    noise_reduction_applied = False
    if apply_noise_reduction:
        audio_array, noise_reduction_applied = _isolate_voice(audio_array)

    try:
        clf = _ModelSingleton.get()
        raw_scores = clf({"array": audio_array, "sampling_rate": TARGET_SAMPLE_RATE}, top_k=None)
    except Exception as exc:
        raise DetectionServiceError(f"Model inference failed: {exc}") from exc

    cloned_probability, match_info = _normalize_scores(raw_scores)
    risk_level = _band_risk(cloned_probability, thresholds)
    risk_score = round(cloned_probability * 100, 1)
    risk_factors = _compute_risk_factors(audio_array, duration, cloned_probability)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "cloned_probability": round(cloned_probability, 4),
        "risk_factors": risk_factors,
        "raw_model_output": {"scores": raw_scores, **match_info},
        "model_name": settings.DETECTION_MODEL_NAME,
        "noise_reduction_applied": noise_reduction_applied,
        "processing_time_ms": elapsed_ms,
        "duration_seconds": round(duration, 2),
        "sample_rate": TARGET_SAMPLE_RATE,
    }
