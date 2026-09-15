from django.contrib import admin

from .models import DetectionPreference, DetectionResult, SecurityAlert, VoiceSample


@admin.register(VoiceSample)
class VoiceSampleAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "user", "source", "file_size_bytes", "duration_seconds", "uploaded_at")
    list_filter = ("source", "uploaded_at")
    search_fields = ("original_filename", "user__username")


@admin.register(DetectionResult)
class DetectionResultAdmin(admin.ModelAdmin):
    list_display = ("id", "sample", "user", "risk_level", "risk_score", "noise_reduction_applied", "created_at")
    list_filter = ("risk_level", "noise_reduction_applied", "created_at")
    search_fields = ("sample__original_filename", "user__username")
    readonly_fields = ("raw_model_output", "risk_factors")


@admin.register(DetectionPreference)
class DetectionPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "sensitivity", "enable_noise_reduction", "alert_on_high_risk", "updated_at")
    list_filter = ("sensitivity", "enable_noise_reduction", "alert_on_high_risk")
    search_fields = ("user__username",)


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message", "acknowledged", "created_at")
    list_filter = ("acknowledged", "created_at")
    search_fields = ("user__username", "message")
