from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from main.views import (
    AuthPlayerView,
    QuizView,
    QuizListView,
    QuestionQuizListView,
    TeamByChatView,
    TeamViewSet,
    PlanTeamQuizListView,
    PlayerGameEndView,
    TeamGameEndView,
    PlayerUpdateView,
    PlayerLeaderboardView,
    TeamLeaderboardView,
    PlayerNotifyListView,
    PlayerTotalPointsView,
    PlayersTotalPointsView,
    BotTextsDictView,
    BotTextsBulkUpsertView,
    RotatedQuestionListView,
    ConfigViewSet,
)


router = DefaultRouter()
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'configs', ConfigViewSet, basename='config')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/player/', AuthPlayerView.as_view(), name='auth-player'),
    path('quiz/game/<str:quiz_type>/', QuizView.as_view(), name='quiz-single'),
    path('quiz/list/<str:quiz_type>/', QuizListView.as_view(), name='quiz-list'),
    path('question/list/', QuestionQuizListView.as_view(), name='question-list'),
    path('question/rotated/', RotatedQuestionListView.as_view(), name='question-rotated'),
    path('team/<str:chat_username>/', TeamByChatView.as_view(), name='team-by-chat'),
    path('game/plan-game/list/<str:chat_username>/', PlanTeamQuizListView.as_view(), name='plan-team-quiz-list'),
    path('player/game-end/', PlayerGameEndView.as_view(), name='player-game-end'),
    path('team/game-end/<int:team_id>/', TeamGameEndView.as_view(), name='team-game-end'),
    path('player/<int:telegram_id>/', PlayerUpdateView.as_view(), name='player-update'),
    path('player/leaderboard/', PlayerLeaderboardView.as_view(), name='player-leaderboard'),
    path('player/total-points/<str:username>/', PlayerTotalPointsView.as_view(), name='player-total-points'),
    path('player/list/total-points/', PlayersTotalPointsView.as_view(), name='players-total-points'),
    path('team/leaderboard/<str:chat_username>/', TeamLeaderboardView.as_view(), name='team-leaderboard'),
    path('player/notify-list/', PlayerNotifyListView.as_view(), name='player-notify-list'),
    path('bot-texts/', BotTextsDictView.as_view(), name='bot-texts-dict'),
    path('bot-texts/bulk-upsert/', BotTextsBulkUpsertView.as_view(), name='bot-texts-bulk-upsert'),

    path('', include(router.urls)),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
