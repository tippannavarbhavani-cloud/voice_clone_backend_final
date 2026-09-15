from rest_framework import serializers

from .models import DetectionPreference, DetectionResult, SecurityAlert, VoiceSample
from .utils import validate_audio_upload


class VoiceSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceSample
        fields = (
            "id",
            "original_filename",
            "file_size_bytes",
            "duration_seconds",
            "sample_rate",
            "source",
            "uploaded_at",
        )
        read_only_fields = fields


class DetectionResultSerializer(serializers.ModelSerializer):
    """Used for the History list — one row per past analysis."""

    sample = VoiceSampleSerializer(read_only=True)

    class Meta:
        model = DetectionResult
        fields = (
            "id",
            "sample",
            "risk_level",
            "risk_score",
            "cloned_probability",
            "model_name",
            "noise_reduction_applied",
            "processing_time_ms",
            "error_message",
            "created_at",
        )
        read_only_fields = fields


class DetectionResultDetailSerializer(DetectionResultSerializer):
    """Adds risk_factors + raw model output — for "View details" and the Analyze result."""

    class Meta(DetectionResultSerializer.Meta):
        fields = DetectionResultSerializer.Meta.fields + ("risk_factors", "raw_model_output")


class AudioUploadSerializer(serializers.Serializer):
    """Input serializer for the file-upload analyze endpoint (also covers recordings)."""

    audio_file = serializers.FileField()
    source = serializers.ChoiceField(
        choices=["upload", "recording"], default="upload", required=False
    )

    def validate_audio_file(self, value):
        return validate_audio_upload(value)


class AudioURLSerializer(serializers.Serializer):
    """Input serializer for the analyze-by-URL endpoint."""

    audio_url = serializers.URLField()


class DetectionPreferenceSerializer(serializers.ModelSerializer):
    """Backs the Settings page."""

    class Meta:
        model = DetectionPreference
        fields = (
            "sensitivity",
            "enable_noise_reduction",
            "alert_on_high_risk",
            "require_reverification_on_high_risk",
            "retain_history_days",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class SecurityAlertSerializer(serializers.ModelSerializer):
    detection_result = DetectionResultSerializer(read_only=True)

    class Meta:
        model = SecurityAlert
        fields = ("id", "detection_result", "message", "acknowledged", "acknowledged_at", "created_at")
        read_only_fields = ("id", "detection_result", "message", "created_at")
