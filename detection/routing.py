from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/live-detect/$", consumers.LiveCallConsumer.as_asgi()),
]
