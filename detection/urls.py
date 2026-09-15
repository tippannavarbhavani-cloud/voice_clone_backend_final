from django.urls import path

from .views import (
    AcknowledgeSecurityAlertView,
    AnalyzeVoiceFromURLView,
    AnalyzeVoiceView,
    DashboardView,
    DetectionHistoryListView,
    DetectionPreferenceView,
    DetectionResultDetailView,
    SecurityAlertListView,
)

urlpatterns = [
    # Analyze page
    path("analyze/", AnalyzeVoiceView.as_view(), name="detection-analyze"),
    path("analyze-url/", AnalyzeVoiceFromURLView.as_view(), name="detection-analyze-url"),

    # Dashboard page
    path("dashboard/", DashboardView.as_view(), name="detection-dashboard"),

    # History page
    path("history/", DetectionHistoryListView.as_view(), name="detection-history"),
    path("history/<int:pk>/", DetectionResultDetailView.as_view(), name="detection-detail"),

    # Settings page
    path("preferences/", DetectionPreferenceView.as_view(), name="detection-preferences"),

    # Security alerts (prevention log)
    path("alerts/", SecurityAlertListView.as_view(), name="detection-alerts"),
    path("alerts/<int:pk>/acknowledge/", AcknowledgeSecurityAlertView.as_view(), name="detection-alert-ack"),
]
