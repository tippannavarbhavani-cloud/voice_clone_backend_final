import logging
from collections import Counter
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DetectionPreference, DetectionResult, SecurityAlert, VoiceSample
from .serializers import (
    AudioUploadSerializer,
    AudioURLSerializer,
    DetectionPreferenceSerializer,
    DetectionResultDetailSerializer,
    DetectionResultSerializer,
    SecurityAlertSerializer,
)
from .services import DetectionServiceError, analyze_audio_file
from .utils import validate_and_fetch_audio_url

logger = logging.getLogger("detection")


def get_or_create_preference(user) -> DetectionPreference:
    preference, _ = DetectionPreference.objects.get_or_create(user=user)
    return preference


def _run_detection_and_save(sample: VoiceSample, user) -> tuple[DetectionResult, bool]:
    """
    Shared by every "analyze this VoiceSample" entry point (upload,
    recording, URL). Runs the model using the user's saved preferences,
    saves a DetectionResult either way, auto-raises a SecurityAlert on
    High Risk if the user has that enabled, and returns (result, succeeded).
    """
    preference = get_or_create_preference(user)

    try:
        result_data = analyze_audio_file(
            sample.audio_file.path,
            thresholds=preference.get_thresholds(),
            apply_noise_reduction=preference.enable_noise_reduction,
        )
        sample.duration_seconds = result_data["duration_seconds"]
        sample.sample_rate = result_data["sample_rate"]
        sample.save(update_fields=["duration_seconds", "sample_rate"])

        result = DetectionResult.objects.create(
            sample=sample,
            user=user,
            risk_level=result_data["risk_level"],
            risk_score=result_data["risk_score"],
            cloned_probability=result_data["cloned_probability"],
            risk_factors=result_data["risk_factors"],
            raw_model_output=result_data["raw_model_output"],
            model_name=result_data["model_name"],
            noise_reduction_applied=result_data["noise_reduction_applied"],
            processing_time_ms=result_data["processing_time_ms"],
        )

        if result.risk_level == DetectionResult.RiskLevel.HIGH_RISK and preference.alert_on_high_risk:
            SecurityAlert.objects.create(
                user=user,
                detection_result=result,
                message=(
                    f"High risk voice clone detected in '{sample.original_filename}' "
                    f"(risk score {result.risk_score:.0f}/100)."
                ),
            )

        return result, True

    except DetectionServiceError as exc:
        logger.warning("Detection failed for sample %s: %s", sample.id, exc)
        result = DetectionResult.objects.create(
            sample=sample,
            user=user,
            risk_level=DetectionResult.RiskLevel.FAILED,
            risk_score=0.0,
            cloned_probability=0.0,
            model_name="n/a",
            error_message=str(exc),
        )
        return result, False


class AnalyzeVoiceView(APIView):
    """
    POST /api/detection/analyze/
    multipart/form-data: { "audio_file": <file>, "source": "upload" | "recording" }

    Covers both plain file uploads and browser microphone recordings.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        input_serializer = AudioUploadSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        uploaded_file = input_serializer.validated_data["audio_file"]
        source = input_serializer.validated_data.get("source", VoiceSample.Source.UPLOAD)

        sample = VoiceSample.objects.create(
            user=request.user,
            audio_file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size_bytes=uploaded_file.size,
            source=source,
        )

        result, succeeded = _run_detection_and_save(sample, request.user)
        response_status = status.HTTP_201_CREATED if succeeded else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(DetectionResultDetailSerializer(result).data, status=response_status)


class AnalyzeVoiceFromURLView(APIView):
    """
    POST /api/detection/analyze-url/
    JSON: { "audio_url": "https://example.com/sample.wav" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        input_serializer = AudioURLSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        url = input_serializer.validated_data["audio_url"]

        content, filename = validate_and_fetch_audio_url(url)

        sample = VoiceSample.objects.create(
            user=request.user,
            audio_file=ContentFile(content, name=filename),
            original_filename=filename,
            file_size_bytes=len(content),
            source=VoiceSample.Source.URL,
        )

        result, succeeded = _run_detection_and_save(sample, request.user)
        response_status = status.HTTP_201_CREATED if succeeded else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(DetectionResultDetailSerializer(result).data, status=response_status)


class DetectionHistoryListView(generics.ListAPIView):
    """
    GET /api/detection/history/?risk_level=high_risk&source=recording
    Backs the "History" page: previous analyses, date/time, risk score,
    Genuine/Suspicious/High Risk, and a link to view details.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DetectionResultSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["risk_level"]

    def get_queryset(self):
        qs = (
            DetectionResult.objects.filter(user=self.request.user)
            .select_related("sample")
            .order_by("-created_at")
        )
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(sample__source=source)
        return qs


class DetectionResultDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /api/detection/history/<id>/   -> full detail incl. risk factors ("View details")
    DELETE /api/detection/history/<id>/   -> remove a result and its audio file
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DetectionResultDetailSerializer

    def get_queryset(self):
        return DetectionResult.objects.filter(user=self.request.user).select_related("sample")

    def perform_destroy(self, instance):
        sample = instance.sample
        instance.delete()
        if sample:
            sample.audio_file.delete(save=False)
            sample.delete()


class DashboardView(APIView):
    """
    GET /api/detection/dashboard/
    Backs the "Dashboard" page: current risk status, risk score, recent
    detections, risk factor breakdown, and stats for a chart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = DetectionResult.objects.filter(user=request.user).exclude(
            risk_level=DetectionResult.RiskLevel.FAILED
        )
        latest = qs.order_by("-created_at").first()

        recent = qs.order_by("-created_at")[:5]

        # Risk factor frequency over the last 30 days, top 5.
        since = timezone.now() - timedelta(days=30)
        factor_counter = Counter()
        for result in qs.filter(created_at__gte=since).only("risk_factors"):
            factor_counter.update(result.risk_factors or [])
        top_factors = [
            {"factor": factor, "count": count}
            for factor, count in factor_counter.most_common(5)
        ]

        # Daily counts for the last 7 days, chart-ready.
        chart_days = []
        for i in range(6, -1, -1):
            day = (timezone.now() - timedelta(days=i)).date()
            day_qs = qs.filter(created_at__date=day)
            chart_days.append({
                "date": day.isoformat(),
                "genuine": day_qs.filter(risk_level=DetectionResult.RiskLevel.GENUINE).count(),
                "suspicious": day_qs.filter(risk_level=DetectionResult.RiskLevel.SUSPICIOUS).count(),
                "high_risk": day_qs.filter(risk_level=DetectionResult.RiskLevel.HIGH_RISK).count(),
            })

        return Response({
            "current_risk_status": latest.risk_level if latest else "no_data",
            "current_risk_score": latest.risk_score if latest else None,
            "recent_detections": DetectionResultSerializer(recent, many=True).data,
            "top_risk_factors": top_factors,
            "detection_statistics": {
                "total_analyses": qs.count(),
                "genuine_count": qs.filter(risk_level=DetectionResult.RiskLevel.GENUINE).count(),
                "suspicious_count": qs.filter(risk_level=DetectionResult.RiskLevel.SUSPICIOUS).count(),
                "high_risk_count": qs.filter(risk_level=DetectionResult.RiskLevel.HIGH_RISK).count(),
                "daily_chart": chart_days,
            },
        })


class DetectionPreferenceView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/detection/preferences/
    Backs the "Settings" page's detection + verification preferences.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DetectionPreferenceSerializer

    def get_object(self):
        return get_or_create_preference(self.request.user)


class SecurityAlertListView(generics.ListAPIView):
    """
    GET /api/detection/alerts/?acknowledged=false
    The "prevention" log — High Risk events an admin/analyst should review.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SecurityAlertSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["acknowledged"]

    def get_queryset(self):
        return SecurityAlert.objects.filter(user=self.request.user).select_related(
            "detection_result", "detection_result__sample"
        )


class AcknowledgeSecurityAlertView(APIView):
    """POST /api/detection/alerts/<id>/acknowledge/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            alert = SecurityAlert.objects.get(pk=pk, user=request.user)
        except SecurityAlert.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        alert.acknowledged = True
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["acknowledged", "acknowledged_at"])
        return Response(SecurityAlertSerializer(alert).data)
