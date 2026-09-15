import uuid

from django.conf import settings
from django.db import models


def user_upload_path(instance, filename):
    """Store each user's uploads under media/audio_uploads/<user_id>/<uuid>_<name>."""
    ext = filename.split(".")[-1]
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    return f"audio_uploads/{instance.user_id}/{safe_name}"


class VoiceSample(models.Model):
    """A submitted audio clip — the raw input, regardless of how it arrived."""

    class Source(models.TextChoices):
        UPLOAD = "upload", "File upload"
        RECORDING = "recording", "Browser microphone recording"
        URL = "url", "Fetched from URL"
        LIVE_CALL = "live_call", "Live call stream"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="voice_samples"
    )
    audio_file = models.FileField(upload_to=user_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.PositiveIntegerField()
    duration_seconds = models.FloatField(null=True, blank=True)
    sample_rate = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.UPLOAD)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.user})"


class DetectionPreference(models.Model):
    """
    Per-user settings — backs the "Settings" page:
    detection preferences, verification preferences, account/system settings.
    """

    class Sensitivity(models.TextChoices):
        STRICT = "strict", "Strict — flags more as risky"
        BALANCED = "balanced", "Balanced"
        LENIENT = "lenient", "Lenient — flags less as risky"

    # (suspicious_from, high_risk_from) cloned-probability thresholds per sensitivity.
    SENSITIVITY_THRESHOLDS = {
        Sensitivity.STRICT: (0.25, 0.55),
        Sensitivity.BALANCED: (0.35, 0.65),
        Sensitivity.LENIENT: (0.45, 0.75),
    }

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="detection_preference"
    )

    # Detection preferences
    sensitivity = models.CharField(max_length=10, choices=Sensitivity.choices, default=Sensitivity.BALANCED)
    enable_noise_reduction = models.BooleanField(default=True)

    # Verification preferences
    alert_on_high_risk = models.BooleanField(default=True)
    require_reverification_on_high_risk = models.BooleanField(
        default=True,
        help_text="If true, a High Risk result should block/flag the workflow until a human re-verifies.",
    )

    # Account/system settings
    retain_history_days = models.PositiveIntegerField(
        default=90, help_text="How long to keep analysis history. 0 = keep forever."
    )

    updated_at = models.DateTimeField(auto_now=True)

    def get_thresholds(self):
        return self.SENSITIVITY_THRESHOLDS[self.sensitivity]

    def __str__(self):
        return f"Preferences for {self.user}"


class DetectionResult(models.Model):
    """The outcome of analyzing a VoiceSample. This is the core audit log row."""

    class RiskLevel(models.TextChoices):
        GENUINE = "genuine", "Genuine"
        SUSPICIOUS = "suspicious", "Suspicious"
        HIGH_RISK = "high_risk", "High Risk"
        FAILED = "failed", "Analysis failed"

    sample = models.OneToOneField(
        VoiceSample, on_delete=models.CASCADE, related_name="detection_result"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="detection_results"
    )

    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, default=RiskLevel.SUSPICIOUS)
    risk_score = models.FloatField(help_text="0-100. Higher = more likely synthetic/cloned.")
    cloned_probability = models.FloatField(help_text="Raw 0.0-1.0 model probability, before risk banding.")
    risk_factors = models.JSONField(
        default=list, blank=True,
        help_text="Human-readable, heuristic signals that contributed to the score.",
    )
    raw_model_output = models.JSONField(default=dict, blank=True)
    model_name = models.CharField(max_length=255)
    noise_reduction_applied = models.BooleanField(default=False)
    processing_time_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["risk_level"]),
        ]

    def __str__(self):
        return f"{self.sample.original_filename}: {self.risk_level} ({self.risk_score:.0f})"


class SecurityAlert(models.Model):
    """
    Auto-created whenever a High Risk result comes in (if the user's
    preferences have alert_on_high_risk enabled). This is the
    "prevention" half of the system — a log an admin/analyst can review
    and acknowledge, separate from the raw detection history.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_alerts"
    )
    detection_result = models.OneToOneField(
        DetectionResult, on_delete=models.CASCADE, related_name="security_alert"
    )
    message = models.CharField(max_length=500)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Alert for {self.user}: {self.message[:50]}"
