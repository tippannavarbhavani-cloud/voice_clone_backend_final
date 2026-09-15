import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# NOTE: get_asgi_application() must run before importing anything that
# touches Django models (like detection.routing -> detection.consumers),
# since it's what sets up Django's app registry.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
import detection.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(detection.routing.websocket_urlpatterns),
    }
)
