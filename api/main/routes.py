from django.urls import re_path
from .consumers import QuizConsumer

websocket_urlpatterns = [
    re_path(
        r'^ws/group-quiz/(?P<game_type>team|deathmatch)/(?P<chat_username>[^/]+)/(?P<quiz_id>\d+)/$',
        QuizConsumer.as_asgi()
    ),
]
