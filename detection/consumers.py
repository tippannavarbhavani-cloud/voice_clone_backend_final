"""
Live-call voice clone detection over a WebSocket.

Connect to:  ws://<host>/ws/live-detect/?token=<JWT access token>

Protocol:
- Client streams raw binary audio chunks as they're recorded
  (e.g. from the browser's MediaRecorder, webm/opus works best).
- Every LIVE_CALL_CHUNKS_PER_ANALYSIS chunks, the server tries to
  decode everything buffered so far and sends back a "partial" verdict.
- Client sends the text message "stop" to end the call: the full
  buffered audio is saved to the database (like any other analysis)
  and a "final" verdict is sent back before the socket closes.

IMPORTANT LIMITATION: compressed audio containers (webm/ogg) are only
guaranteed to decode cleanly once a full/valid file is available, so
early "partial" updates may occasionally be skipped if there isn't
enough audio yet to decode. This is expected — treat partial verdicts
as best-effort live feedback, and the "final" verdict as authoritative.
"""
import json
import logging
import os
import tempfile
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import DetectionResult, SecurityAlert, VoiceSample
from .services import DetectionServiceError, analyze_audio_file
from .views import get_or_create_preference

logger = logging.getLogger("detection")


class LiveCallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)  # auth failed
            return

        self.user = user
        self.buffer = bytearray()
        self.chunk_count = 0
        self.tmp_dir = tempfile.mkdtemp(prefix="live_call_")

        await self.accept()
        await self.send(json.dumps({"type": "connected", "message": "Live detection ready."}))

    async def disconnect(self, close_code):
        self._cleanup_tmp_dir()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data == "stop":
            await self._finalize()
            await self.close(code=1000)
            return

        if bytes_data:
            self.buffer.extend(bytes_data)
            self.chunk_count += 1
            if self.chunk_count % settings.LIVE_CALL_CHUNKS_PER_ANALYSIS == 0:
                await self._try_partial_analysis()

    async def _try_partial_analysis(self):
        tmp_path = os.path.join(self.tmp_dir, "partial.webm")
        with open(tmp_path, "wb") as f:
            f.write(self.buffer)

        try:
            preference = await database_sync_to_async(get_or_create_preference)(self.user)
            result = await database_sync_to_async(analyze_audio_file)(
                tmp_path,
                thresholds=preference.get_thresholds(),
                apply_noise_reduction=preference.enable_noise_reduction,
            )
            await self.send(json.dumps({
                "type": "partial",
                "risk_level": result["risk_level"],
                "risk_score": result["risk_score"],
                "cloned_probability": result["cloned_probability"],
            }))
        except DetectionServiceError:
            # Not enough / not-yet-decodable audio — wait for more chunks.
            pass
        except Exception as exc:
            logger.warning("Live partial analysis error: %s", exc)

    async def _finalize(self):
        if not self.buffer:
            await self.send(json.dumps({"type": "final", "error": "No audio was received."}))
            return

        final_path = os.path.join(self.tmp_dir, "final.webm")
        with open(final_path, "wb") as f:
            f.write(self.buffer)

        preference = await database_sync_to_async(get_or_create_preference)(self.user)
        try:
            result_data = await database_sync_to_async(analyze_audio_file)(
                final_path,
                thresholds=preference.get_thresholds(),
                apply_noise_reduction=preference.enable_noise_reduction,
            )
        except DetectionServiceError as exc:
            await self.send(json.dumps({"type": "final", "error": str(exc)}))
            return

        await database_sync_to_async(self._save_result)(final_path, result_data, preference)

        await self.send(json.dumps({
            "type": "final",
            "risk_level": result_data["risk_level"],
            "risk_score": result_data["risk_score"],
            "cloned_probability": result_data["cloned_probability"],
            "risk_factors": result_data["risk_factors"],
        }))

    def _save_result(self, final_path, result_data, preference):
        """Runs in a thread (via database_sync_to_async) — safe to touch the ORM here."""
        from django.core.files import File

        with open(final_path, "rb") as f:
            sample = VoiceSample.objects.create(
                user=self.user,
                audio_file=File(f, name=f"live_call_{int(time.time())}.webm"),
                original_filename="live_call.webm",
                file_size_bytes=os.path.getsize(final_path),
                duration_seconds=result_data["duration_seconds"],
                sample_rate=result_data["sample_rate"],
                source=VoiceSample.Source.LIVE_CALL,
            )

        result = DetectionResult.objects.create(
            sample=sample,
            user=self.user,
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
                user=self.user,
                detection_result=result,
                message=f"High risk voice clone detected during a live call (risk score {result.risk_score:.0f}/100).",
            )

    @database_sync_to_async
    def _authenticate(self):
        """Browsers can't set custom headers on a WebSocket, so the JWT
        access token is passed as a query string param instead:
        ws://host/ws/live-detect/?token=<access_token>
        """
        query_string = self.scope.get("query_string", b"").decode()
        token_str = None
        for param in query_string.split("&"):
            if param.startswith("token="):
                token_str = param.split("=", 1)[1]
                break

        if not token_str:
            return None

        try:
            access = AccessToken(token_str)
            return User.objects.get(id=access["user_id"])
        except (TokenError, User.DoesNotExist, KeyError):
            return None

    def _cleanup_tmp_dir(self):
        try:
            for name in os.listdir(self.tmp_dir):
                os.remove(os.path.join(self.tmp_dir, name))
            os.rmdir(self.tmp_dir)
        except Exception:
            pass
