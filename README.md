# Voice Clone Impersonation Detection — Backend

Django + DRF backend for real-time detection of AI-generated / cloned
voices, built around the "AI-Powered Real-Time Detection and Prevention
of Voice Cloning Impersonation Attacks" problem statement.

## What it does

- Accepts audio via **file upload (mp3/wav/etc), browser recording,
  a URL, or a live call stream (WebSocket)**
- Runs **voice isolation** (background noise reduction) before analysis
- Scores each clip **0-100** and bands it into **Genuine / Suspicious /
  High Risk**
- Explains *why* with human-readable **risk factors**
- Auto-logs a **Security Alert** for High Risk results (the "prevention" half)
- Exposes everything the 4 frontend pages need: **Dashboard, Analyze,
  History, Settings**

## Stack

- Django 5 + Django REST Framework, JWT auth (`djangorestframework-simplejwt`)
- MySQL locally (`mysqlclient`) — see `.env` for `DATABASE_ENGINE`
- Detection: pretrained HuggingFace `audio-classification` model via
  `transformers` + `torch`, audio decoded with `librosa`
- Voice isolation: `noisereduce` (spectral gating noise reduction)
- Live calls: `channels` + `daphne` (WebSockets)

## The database / logs

Every analysis is a row in `detection_detectionresult`, linked to the
`detection_voicesample` row for the audio that was analyzed. Together
these two tables ARE your log: who submitted what, when, from which
input method, what the risk score was, and why. Nothing needs to be
logged separately — querying `DetectionResult` (e.g. in Django admin,
or via `/api/detection/history/`) *is* your audit trail.

```
VoiceSample            DetectionResult              SecurityAlert
------------            ---------------              -------------
user                    sample (1:1)                 user
audio_file              user                         detection_result (1:1)
original_filename       risk_level                   message
file_size_bytes         risk_score (0-100)           acknowledged
duration_seconds        cloned_probability           acknowledged_at
sample_rate             risk_factors (JSON list)      created_at
source (upload/         raw_model_output (JSON)
  recording/url/         model_name
  live_call)             noise_reduction_applied
uploaded_at             processing_time_ms
                        error_message
                        created_at

DetectionPreference (per-user Settings)
----------------------------------------
user (1:1)
sensitivity (strict/balanced/lenient)
enable_noise_reduction
alert_on_high_risk
require_reverification_on_high_risk
retain_history_days
```

### Creating the database

```sql
CREATE DATABASE voice_clone_db CHARACTER SET utf8mb4;
CREATE USER 'vcd_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON voice_clone_db.* TO 'vcd_user'@'localhost';
FLUSH PRIVILEGES;
```

Then, as usual:
```bash
python manage.py makemigrations
python manage.py migrate
```
This creates all four tables above (plus Django's own auth tables) automatically — you never write raw `CREATE TABLE` SQL for the app's own log tables; Django's migrations do it from the models.

## Setup

```bash
cp .env.example .env      # then fill in your DB credentials + SECRET_KEY
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8001
```

> First request that runs analysis will be slow — it downloads the AI
> model from HuggingFace Hub the first time, then caches it locally.

## API reference

All endpoints are prefixed `/api/`. JWT-protected ones expect
`Authorization: Bearer <access_token>`.

### Auth (`/api/auth/`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `register/` | Create account, returns JWT pair |
| POST | `login/` | `{username, password}` → JWT pair |
| POST | `refresh/` | `{refresh}` → new access token |
| POST | `logout/` | Blacklists a refresh token |
| GET/PATCH | `profile/` | View/update your account (Settings page) |

### Analyze page (`/api/detection/`)
| Method | Endpoint | Description |
|---|---|---|
| POST | `analyze/` | multipart `audio_file` (+ optional `source`: `upload`/`recording`) |
| POST | `analyze-url/` | JSON `{"audio_url": "..."}` |
| WS | `ws/live-detect/?token=<access>` | Live call streaming — see below |

All three return the same shape:
```json
{
  "id": 12,
  "sample": {"original_filename": "call.wav", "source": "upload", "duration_seconds": 6.1, ...},
  "risk_level": "high_risk",
  "risk_score": 87.3,
  "cloned_probability": 0.873,
  "risk_factors": [
    "Acoustic classifier strongly matched patterns typical of synthetic speech.",
    "Unusually consistent pitch — natural speech typically has more variation."
  ],
  "noise_reduction_applied": true,
  "processing_time_ms": 940,
  "created_at": "2026-09-11T10:15:01Z"
}
```

### Live call (WebSocket)
```
ws://127.0.0.1:8001/ws/live-detect/?token=<JWT access token>
```
- Stream raw binary audio chunks (e.g. `MediaRecorder`).
- Server periodically sends `{"type": "partial", "risk_level": ..., "risk_score": ...}`.
- Send the text message `"stop"` to end — server saves the full clip to
  history/alerts and sends `{"type": "final", ...}` before closing.
- A ready-to-use test page is at `test_page.html` in the project root.

### Dashboard page
| Method | Endpoint | Description |
|---|---|---|
| GET | `dashboard/` | current risk status, risk score, recent detections, top risk factors, chart-ready daily stats |

### History page
| Method | Endpoint | Description |
|---|---|---|
| GET | `history/?risk_level=high_risk&source=recording` | paginated list, filterable |
| GET | `history/<id>/` | full detail incl. risk factors ("View details") |
| DELETE | `history/<id>/` | remove a result + its audio file |

### Settings page
| Method | Endpoint | Description |
|---|---|---|
| GET/PATCH | `preferences/` | sensitivity, noise reduction toggle, alert/verification preferences, retention |
| GET/PATCH | `/api/auth/profile/` | account settings (username/email) |

### Prevention log
| Method | Endpoint | Description |
|---|---|---|
| GET | `alerts/?acknowledged=false` | High Risk events that fired an alert |
| POST | `alerts/<id>/acknowledge/` | mark an alert reviewed |

## Voice isolation (noise reduction)

Every clip is passed through spectral-gating noise reduction
(`noisereduce`) before analysis, unless the user has disabled it in
their preferences. If the library errors on a particular clip (rare),
the pipeline falls back to the original audio rather than failing the
whole request — this is reported back via `noise_reduction_applied: false`.

## Risk scoring

`cloned_probability` (0.0-1.0, from the pretrained model) is converted
to a 0-100 `risk_score` and banded using the user's **sensitivity**
setting:

| Sensitivity | Suspicious from | High Risk from |
|---|---|---|
| Strict | 25% | 55% |
| Balanced (default) | 35% | 65% |
| Lenient | 45% | 75% |

`risk_factors` are heuristic, explainable signals (spectral flatness,
pitch consistency, clip duration, model confidence) — useful context
for a reviewer, not independently validated forensic claims.

## Swapping the detection model

Everything model-specific lives in `detection/services.py`. Set
`DETECTION_MODEL_NAME` in `.env` to any HuggingFace Hub model that
supports the `audio-classification` pipeline. If its labels aren't
`spoof/bonafide` or `fake/real`, add them to `SYNTHETIC_LABELS` /
`AUTHENTIC_LABELS` in `services.py`.

## Notes & next steps

- **Async processing**: inference runs synchronously in the request
  today. For real scale, move `analyze_audio_file` into a Celery task.
- **"Good loading animation"** from the spec is a frontend concern —
  this backend supports it by returning quickly-checkable status; the
  frontend should show a spinner/progress state between the `analyze`
  request and its response (typically 1-3 seconds after the model is
  warm).
- **Storage**: audio files are stored on local disk under `media/`.
  Swap in `django-storages` (S3/GCS) for production.
- **retain_history_days** in preferences is a stored setting — wire it
  up to a scheduled cleanup task (Celery beat / cron) when you're ready
  to actually enforce retention.
