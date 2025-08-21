from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, permissions, serializers
from django.utils import timezone
from django.utils.timezone import now

from datetime import timedelta, datetime
import random
import pytz

from .models import TelegramPlayer, Quiz, PlayerToken, Team, PlanTeamQuiz
from .serializers import (
    AuthPlayerSerializer, QuizInfoSerializer, QuestionListSerializer, TeamSerializer,
    PlanTeamQuizSerializer, TelegramPlayerUpdateSerializer, LeaderboardEntrySerializer,
)
from .authentication import PlayerTokenAuthentication, SystemTokenAuthentication


class AuthPlayerView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AuthPlayerSerializer(data=request.data)
        serializer.is_valid()

        data = serializer.validated_data
        telegram_id = data['telegram_id']

        defaults = {
            'first_name': data.get('first_name'),
            'last_name': data.get('last_name'),
            'username': data.get('username'),
            'phone': data.get('phone'),
            'lang_code': data.get('lang_code'),
        }

        player, _ = TelegramPlayer.objects.update_or_create(
            telegram_id=telegram_id,
            defaults={k: v for k, v in defaults.items() if v is not None}
        )
        token, _ = PlayerToken.objects.get_or_create(player=player)

        return Response({'token': token.key})


class QuizView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, quiz_type):
        quiz_id = request.query_params.get('quiz_id')

        if not quiz_id:
            quiz = Quiz.objects.filter(quiz_type=quiz_type).last()
        else:
            quiz = Quiz.objects.filter(id=quiz_id).last()

        if not quiz:
            return Response({'detail': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = QuizInfoSerializer(quiz)
        return Response(serializer.data)


class QuizListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, quiz_type):
        """Вернуть список всех активных квизов выбранного типа."""
        quizzes = Quiz.objects.filter(quiz_type=quiz_type).order_by('id')
        serializer = QuizInfoSerializer(quizzes, many=True)
        return Response(serializer.data)


class QuestionListView(APIView):
    authentication_classes = [PlayerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        quiz_id = request.query_params.get('quiz_id')

        if not quiz_id:
            return Response({'detail': 'quiz_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({'detail': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)

        all_questions = list(quiz.questions.all())
        random.shuffle(all_questions)

        selected = all_questions[:quiz.amount_questions]
        # Передаем time_to_answer из Quiz в контекст сериализатора, чтобы оно добавилось к каждому вопросу
        serializer = QuestionListSerializer(selected, many=True, context={'time_to_answer': quiz.time_to_answer})

        return Response(serializer.data)


class TeamViewSet(viewsets.ModelViewSet):
    authentication_classes = [PlayerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TeamSerializer
    queryset = Team.objects.all()

    def create(self, request, *args, **kwargs):
        # Получаем player_id из данных запроса
        player_id = request.data.get('player_id')
        
        if player_id:
            try:
                telegram_user = TelegramPlayer.objects.get(telegram_id=player_id)
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save(captain=telegram_user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except TelegramPlayer.DoesNotExist:
                return Response(
                    {'error': f'Player with telegram_id {player_id} not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            raise serializers.ValidationError('player_id is required')


class PlanTeamQuizListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        current_time = datetime.now(pytz.timezone('Europe/Moscow')).date()

        items = PlanTeamQuiz.objects.filter(
            scheduled_datetime__gte=current_time,
        ).select_related('quiz').order_by('id')

        serializer = PlanTeamQuizSerializer(items, many=True)
        return Response(serializer.data)


class PlayerTotalPointsView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, username):
        player = TelegramPlayer.objects.filter(username=username).first()

        if not player:
            return Response({'detail': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'total_points': player.total_xp})


class PlayersTotalPointsView(APIView):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data
        players = TelegramPlayer.objects.filter(username__in=payload['usernames']).values('username', 'total_xp')
        return Response(list(players))


class PlayerGameEndView(APIView):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data
        if isinstance(payload, dict) and isinstance(payload.get('results'), list):
            entries = payload['results']
        elif isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict) and 'username' in payload:
            entries = [payload]
        else:
            return Response({'detail': 'Expected a list of {username, points}'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        updated = []
        not_found = []

        for item in entries:
            username = item.get('username')
            points = int(item.get('points', 0) or 0)
            if not username:
                continue
            try:
                player = TelegramPlayer.objects.get(username=username)
            except TelegramPlayer.DoesNotExist:
                not_found.append(username)
                continue

            # Стрик: сравнение с today - 2
            last = player.last_played_at
            if points > 0:
                today = now.date()
                threshold = today.toordinal() - 2  # today - 2 дня
                last_ord = last.date().toordinal() if last else None
                if last is None or (last_ord is not None and last_ord < threshold):
                    player.current_streak = 1
                else:
                    if last.date() != today:
                        player.current_streak = (player.current_streak or 0) + 1

            player.total_xp = (player.total_xp or 0) + max(0, points)
            player.last_played_at = now
            player.save(update_fields=['total_xp', 'last_played_at', 'current_streak'])
            updated.append({'username': username, 'streak': player.current_streak, 'total_xp': player.total_xp})

        return Response({'updated': updated, 'not_found': not_found})
 

class TeamGameEndView(APIView):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, team_id):
        points = int(request.data.get('points', 0))
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'detail': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)
        team.total_scores = (team.total_scores or 0) + max(0, points)
        team.save(update_fields=['total_scores'])
        return Response({'total_scores': team.total_scores})


class PlayerUpdateView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    def patch(self, request, telegram_id):
        try:
            player = TelegramPlayer.objects.get(telegram_id=telegram_id)
        except TelegramPlayer.DoesNotExist:
            return Response({'detail': 'Player not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TelegramPlayerUpdateSerializer(player, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'ok': True})


class PlayerLeaderboardView(APIView):
    def get(self, request):
        qs = TelegramPlayer.objects.order_by('-total_xp')
        top = list(qs[:50])
        data = [{'username': p.username or str(p.telegram_id), 'total_xp': p.total_xp} for p in top]
        serializer = LeaderboardEntrySerializer(data, many=True)
        # Позиция текущего пользователя, если аутентифицирован
        current = None
        if isinstance(request.user, TelegramPlayer):
            # Найдем позицию в общем queryset
            # Оптимизация опущена для простоты
            ordered_ids = list(qs.values_list('id', flat=True))
            try:
                pos = ordered_ids.index(request.user.id) + 1
            except ValueError:
                pos = None
            current = {
                'position': pos,
                'total': qs.count(),
                'streak': request.user.current_streak,
            }
        return Response({'entries': serializer.data, 'current': current})


class TeamLeaderboardView(APIView):
    def get(self, request):
        teams = Team.objects.order_by('-total_scores')[:50]
        data = [{'username': t.name, 'total_xp': t.total_scores} for t in teams]
        serializer = LeaderboardEntrySerializer(data, many=True)
        return Response(serializer.data)


class TeamByChatView(APIView):
    authentication_classes = [PlayerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TeamSerializer

    def get(self, request, chat_username):
        team = Team.objects.filter(chat_username=chat_username).first()
        
        if team is not None:
            team_serializer = TeamSerializer(team)
            return Response(team_serializer.data)
        else:
            return Response({'detail': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)


class PlayerNotifyListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        players = TelegramPlayer.objects.filter(notification_is_on=True).values('telegram_id', 'username')
        return Response(list(players))
