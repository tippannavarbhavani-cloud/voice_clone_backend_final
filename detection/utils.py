import ipaddress
import os
import socket
from urllib.parse import urlparse

import requests
from django.conf import settings
from rest_framework import serializers

# Maps common audio Content-Type headers to a file extension, used when
# a URL doesn't end in a recognizable extension (e.g. a signed/query-string URL).
CONTENT_TYPE_TO_EXTENSION = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/webm": ".webm",
}


def validate_audio_upload(uploaded_file):
    """Raise a DRF ValidationError if the uploaded file fails basic sanity checks."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
        raise serializers.ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_AUDIO_EXTENSIONS)}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise serializers.ValidationError(
            f"File too large ({uploaded_file.size / (1024 * 1024):.1f} MB). "
            f"Max is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    if uploaded_file.size == 0:
        raise serializers.ValidationError("Uploaded file is empty.")

    return uploaded_file


def validate_and_fetch_audio_url(url: str) -> tuple[bytes, str]:
    """
    Download audio from a user-supplied URL for the "analyze by URL"
    feature. Returns (content_bytes, filename).

    Includes basic SSRF (server-side request forgery) protection:
    only plain http/https URLs are allowed, and the resolved IP must
    not point at a private/internal/loopback address — otherwise a
    malicious URL could be used to make this server probe your own
    internal network (e.g. http://169.254.169.254/, http://localhost/, etc).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise serializers.ValidationError("URL must start with http:// or https://")
    if not parsed.hostname:
        raise serializers.ValidationError("That doesn't look like a valid URL.")

    try:
        resolved_ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(resolved_ip)
    except (socket.gaierror, ValueError):
        raise serializers.ValidationError("Could not resolve that host.")

    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
        raise serializers.ValidationError(
            "URLs pointing to internal/private network addresses are not allowed."
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    try:
        response = requests.get(
            url,
            stream=True,
            timeout=settings.URL_DOWNLOAD_TIMEOUT_SECONDS,
            headers={"User-Agent": "VoiceCloneDetector/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise serializers.ValidationError(f"Could not download audio from that URL: {exc}")

    content = bytearray()
    for chunk in response.iter_content(chunk_size=8192):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise serializers.ValidationError(
                f"File from URL exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit."
            )

    if len(content) == 0:
        raise serializers.ValidationError("Downloaded file is empty.")

    filename = os.path.basename(parsed.path) or "downloaded_audio"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        mapped_ext = CONTENT_TYPE_TO_EXTENSION.get(content_type)
        if mapped_ext is None:
            raise serializers.ValidationError(
                "Could not determine a supported audio type from that URL. "
                f"Allowed: {', '.join(settings.ALLOWED_AUDIO_EXTENSIONS)}"
            )
        filename = f"downloaded_audio{mapped_ext}"

    return bytes(content), filename
