from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import DetectionResult, SecurityAlert

FAKE_DETECTION_RESULT = {
    "risk_level": "high_risk",
    "risk_score": 91.0,
    "cloned_probability": 0.91,
    "risk_factors": ["Acoustic classifier strongly matched patterns typical of synthetic speech."],
    "raw_model_output": {"scores": [{"label": "spoof", "score": 0.91}]},
    "model_name": "fake-model-for-testing",
    "noise_reduction_applied": True,
    "processing_time_ms": 5,
    "duration_seconds": 2.0,
    "sample_rate": 16000,
}


class AnalyzeVoiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="voiceuser", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    @patch("detection.views.analyze_audio_file")
    def test_upload_and_analyze_audio(self, mock_analyze):
        mock_analyze.return_value = FAKE_DETECTION_RESULT

        fake_audio = BytesIO(b"fake audio bytes")
        fake_audio.name = "test.wav"

        response = self.client.post(
            "/api/detection/analyze/", {"audio_file": fake_audio}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["risk_level"], "high_risk")
        self.assertEqual(response.data["risk_score"], 91.0)
        self.assertEqual(DetectionResult.objects.count(), 1)

    @patch("detection.views.analyze_audio_file")
    def test_high_risk_creates_security_alert(self, mock_analyze):
        """High risk results should auto-create an alert (prevention log)."""
        mock_analyze.return_value = FAKE_DETECTION_RESULT

        fake_audio = BytesIO(b"fake audio bytes")
        fake_audio.name = "test.wav"

        self.client.post("/api/detection/analyze/", {"audio_file": fake_audio}, format="multipart")

        self.assertEqual(SecurityAlert.objects.filter(user=self.user).count(), 1)

    def test_cannot_analyze_without_login(self):
        self.client.force_authenticate(user=None)
        fake_audio = BytesIO(b"fake audio bytes")
        fake_audio.name = "test.wav"

        response = self.client.post(
            "/api/detection/analyze/", {"audio_file": fake_audio}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_wrong_file_type(self):
        fake_file = BytesIO(b"this is not audio")
        fake_file.name = "notes.txt"

        response = self.client.post(
            "/api/detection/analyze/", {"audio_file": fake_file}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class HistoryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="historyuser", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    def test_history_starts_empty(self):
        response = self.client.get("/api/detection/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)


class DashboardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dashuser", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    def test_dashboard_with_no_history(self):
        response = self.client.get("/api/detection/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_risk_status"], "no_data")
        self.assertEqual(response.data["detection_statistics"]["total_analyses"], 0)


class PreferenceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="prefuser", password="TestPass123!")
        self.client.force_authenticate(user=self.user)

    def test_default_preferences_are_created_automatically(self):
        response = self.client.get("/api/detection/preferences/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sensitivity"], "balanced")
        self.assertTrue(response.data["enable_noise_reduction"])

    def test_can_update_sensitivity(self):
        response = self.client.patch("/api/detection/preferences/", {"sensitivity": "strict"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sensitivity"], "strict")
