from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, permissions, serializers
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse

from datetime import datetime
import random
import pandas as pd
import hashlib

import pytz
from .models import TelegramPlayer, Quiz, PlayerToken, Team, PlanTeamQuiz, BotText, City, Question, QuestionUsage, Config, Topic, QuestionAnswer, Chat, PlayerInChat
from .serializers import (
    AuthPlayerSerializer, QuizInfoSerializer, QuestionListSerializer, TeamSerializer,
    PlanTeamQuizSerializer, TelegramPlayerUpdateSerializer, LeaderboardEntrySerializer,
    BotTextDictSerializer, TeamLeaderboardEntrySerializer, ConfigSerializer,
    ChatLeaderboardEntrySerializer, ChatSerializer
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


class QuestionQuizListView(APIView):
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


class RotatedQuestionListView(APIView):
    """POST: отдаёт список вопросов по use_type (dm/solo) с ротацией по context_id.
    Авторизация: системный токен.
    Тело запроса: { use_type: 'dm'|'solo', context_id: int, size: int, time_to_answer?: int }
    Ответ: { questions: [QuestionListSerializer ...] }
    """
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        use_type = request.data.get('use_type')
        context_id = request.data.get('context_id')
        size = request.data.get('size')
        time_to_answer = request.data.get('time_to_answer')

        # Валидация
        if use_type not in ('dm', 'solo'):
            return Response({'detail': 'use_type must be "dm" or "solo"'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            context_id = int(context_id)
        except Exception:
            return Response({'detail': 'context_id must be integer'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            size = int(size)
        except Exception:
            return Response({'detail': 'size must be integer'}, status=status.HTTP_400_BAD_REQUEST)

        if size <= 0:
            return Response({'detail': 'size must be > 0'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Кандидаты — все вопросы данного типа игры, не использованные в этом контексте
            exists_subq = QuestionUsage.objects.filter(
                use_type=use_type, context_id=context_id, question=OuterRef('pk')
            )
            available_qs = (
                Question.objects
                .filter(game_use_type=use_type)
                .annotate(already_used=Exists(exists_subq))
                .filter(already_used=False)
            )

            # Одним запросом случайно выбираем нужное количество
            selected = list(available_qs.order_by('?')[:size])

            # Если не хватило — сброс истории и выбор из полного пула
            if len(selected) < size:
                QuestionUsage.objects.filter(use_type=use_type, context_id=context_id).delete()
                selected = list(Question.objects.filter(game_use_type=use_type).order_by('?')[:size])

            if not selected:
                return Response({'questions': []})

            # Зафиксировать использование
            usages = [QuestionUsage(use_type=use_type, context_id=context_id, question=q) for q in selected]
            try:
                QuestionUsage.objects.bulk_create(usages, ignore_conflicts=True)
            except Exception:
                pass

        serializer = QuestionListSerializer(selected, many=True, context={'time_to_answer': time_to_answer})
        return Response({'questions': serializer.data})


class ConfigViewSet(viewsets.ModelViewSet):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConfigSerializer
    queryset = Config.objects.all()


class TeamViewSet(viewsets.ModelViewSet):
    authentication_classes = [PlayerTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TeamSerializer
    queryset = Team.objects.all()

    def create(self, request, *args, **kwargs):
        # Получаем player_id из данных запроса
        player_id = request.data.get('player_id')
        city_name = request.data.get('city')  # строка с названием города (опционально)
        
        if not player_id:
            raise serializers.ValidationError('player_id is required')

        try:
            telegram_user = TelegramPlayer.objects.get(telegram_id=player_id)
        except TelegramPlayer.DoesNotExist:
            return Response(
                {'error': f'Player with telegram_id {player_id} not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        # Если передан city как название — попробуем найти City
        if city_name:
            city_obj = City.objects.filter(name__iexact=city_name.strip()).first()
            if city_obj is None:
                city_obj = City.objects.create(name=city_name.strip())
            data['city'] = city_obj.id
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(captain=telegram_user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PlanTeamQuizListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [PlayerTokenAuthentication]

    def get(self, request, chat_username):
        current_time = datetime.now(pytz.timezone('Europe/Moscow')).date()
        team = Team.objects.filter(chat_username=chat_username).first()

        if not team:
            return Response({'detail': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

        items = PlanTeamQuiz.objects.filter(
            Q(scheduled_datetime__gte=current_time) | Q(always_active=True),
        ).exclude(
            teams_played=team
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


class PlayersChatPointsView(APIView):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data
        usernames = payload.get('usernames', [])
        chat_id = payload.get('chat_id')
        
        if not usernames or not chat_id:
            return Response([])

        try:
            chat = Chat.objects.get(chat_id=chat_id)
        except Chat.DoesNotExist:
            return Response([])

        players = TelegramPlayer.objects.filter(username__in=usernames)
        result = []
        for player in players:
            try:
                player_in_chat = PlayerInChat.objects.get(player=player, chat=chat)
                points = player_in_chat.points
            except PlayerInChat.DoesNotExist:
                points = 0
            
            result.append({
                'username': player.username,
                'points': points
            })
        return Response(result)


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
            chat_id = item.get('chat_id')
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

            # Если указан chat_id — учитываем очки в контексте конкретного чата
            try:
                if chat_id is not None:
                    try:
                        chat_id_int = int(chat_id)
                    except Exception:
                        chat_id_int = None
                    if chat_id_int is not None:
                        chat_obj, _ = Chat.objects.get_or_create(chat_id=chat_id_int)
                        pic, _ = PlayerInChat.objects.get_or_create(player=player, chat=chat_obj)
                        pic.points = (pic.points or 0) + max(0, points)
                        pic.last_played_at = now
                        pic.save(update_fields=['points', 'last_played_at'])
            except Exception:
                # Не прерываем весь процесс начисления при локальной ошибке
                pass
            updated.append({'username': username, 'streak': player.current_streak, 'total_xp': player.total_xp})

        return Response({'updated': updated, 'not_found': not_found})


class ChatRegisterView(APIView):
    """Регистрация/апдейт чата по chat_id (и chat_username).
    Авторизация: системный токен.
    Тело: { chat_id: int, chat_username?: str }
    Ответ: { created: bool, id: int }
    """
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            chat_id = int(request.data.get('chat_id'))
        except Exception:
            return Response({'detail': 'chat_id must be integer'}, status=status.HTTP_400_BAD_REQUEST)
        chat_username = request.data.get('chat_username') or None

        chat, created = Chat.objects.update_or_create(
            chat_id=chat_id,
            defaults={'chat_username': chat_username}
        )
        return Response({'created': created, 'id': chat.id})
 

class TeamGameEndView(APIView):
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, team_id):
        points = int(request.data.get('points', 0))
        plan_team_quiz_id = int(request.data.get('plan_team_quiz_id', 0))

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'detail': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

        team.total_scores = (team.total_scores or 0) + max(0, points)
        team.save(update_fields=['total_scores'])
        
        # Добавляем команду как сыгравшую в PlanTeamQuiz
        if plan_team_quiz_id:
            try:
                plan_team_quiz = PlanTeamQuiz.objects.get(id=plan_team_quiz_id)
                plan_team_quiz.teams_played.add(team)
            except PlanTeamQuiz.DoesNotExist:
                pass

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
        top = list(qs[:10])
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

    def post(self, request):
        """Лидерборд среди конкретных пользователей по username"""
        usernames = request.data.get('usernames', [])
        current_user_username = request.data.get('current_user_username', None)

        if not isinstance(usernames, list) or not usernames:
            return Response({'error': 'usernames list is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Фильтруем игроков по username (убираем @ если есть)
        clean_usernames = []
        for username in usernames:
            if isinstance(username, str):
                clean_username = username.lstrip('@').lower()
                if clean_username:
                    clean_usernames.append(clean_username)

        if not clean_usernames:
            return Response({'error': 'No valid usernames provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Получаем игроков по username и сортируем по total_xp
        qs = TelegramPlayer.objects.filter(
            username__in=clean_usernames
        ).order_by('-total_xp')

        current_player = qs.get(username=current_user_username)

        # Формируем данные для ответа
        entries = []
        for player in qs:
            entries.append({
                'username': player.username or str(player.telegram_id),
                'total_xp': player.total_xp
            })

        # Позиция текущего пользователя среди этих игроков
        current = None
        if isinstance(request.user, TelegramPlayer):
            try:
                current_user_pos = None
                for idx, player in enumerate(qs, 1):
                    if player.username == current_player.username:
                        current_user_pos = idx
                        break

                if current_user_pos:
                    current = {
                        'position': current_user_pos,
                        'total': qs.count(),
                        'streak': current_player.current_streak,
                    }
            except Exception:
                pass

        top_5 = entries[:5]

        serializer = LeaderboardEntrySerializer(top_5, many=True)
        return Response({'entries': serializer.data, 'current': current})


class TeamLeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [PlayerTokenAuthentication]

    def get(self, request, chat_username):
        qs = Team.objects.order_by('-total_scores')
        top = list(qs[:10])
        data = [{'username': t.name, 'total_scores': t.total_scores} for t in top]
        serializer = TeamLeaderboardEntrySerializer(data, many=True)

        # Информация о текущей команде
        current = None
        try:
            current_team = Team.objects.get(chat_username=chat_username)
            # Найдем позицию команды в общем рейтинге
            ordered_ids = list(qs.values_list('id', flat=True))
            try:
                pos = ordered_ids.index(current_team.id) + 1
            except ValueError:
                pos = None
            current = {
                'position': pos,
                'total': qs.count(),
                'total_scores': current_team.total_scores,
            }
        except Team.DoesNotExist:
            pass
        
        return Response({'entries': serializer.data, 'current': current})


class ChatLeaderboardView(APIView):
    """Лидерборд игроков в конкретном чате"""
    authentication_classes = [SystemTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, chat_id):
        try:
            # Преобразуем строковый chat_id в число
            chat_id_int = int(chat_id)
            chat = Chat.objects.get(chat_id=chat_id_int)
        except (Chat.DoesNotExist, ValueError):
            return Response({'detail': 'Chat not found'}, status=status.HTTP_404_NOT_FOUND)

        # Получаем топ-10 игроков в этом чате
        player_scores = (
            PlayerInChat.objects
            .filter(chat=chat, points__gt=0)
            .select_related('player')
            .order_by('-points')[:10]
        )

        entries = []
        for ps in player_scores:
            entries.append({
                'username': ps.player.username or str(ps.player.telegram_id),
                'points': ps.points,
                'first_name': ps.player.first_name,
                'last_name': ps.player.last_name or ''
            })

        serializer = ChatLeaderboardEntrySerializer(entries, many=True)
        return Response({'entries': serializer.data})


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


class BotTextsDictView(APIView):
    """Возвращает все BotText в формате словаря, где ключ - text_name, значение - объект."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SystemTokenAuthentication]

    def get(self, request):
        serializer = BotTextDictSerializer(BotText.objects.all(), many=True)
        return Response(serializer.data)


class BotTextsBulkUpsertView(APIView):
    """Bulk upsert для BotText записей."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SystemTokenAuthentication]

    def post(self, request):
        texts = request.data.get('texts', [])
        if not isinstance(texts, list):
            return Response({'error': 'Expected "texts" to be a list'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        updated_count = 0

        for text_data in texts:
            text_name = text_data.get('text_name')
            if not text_name:
                continue
            
            defaults = {
                'label': text_data.get('label', ''),
                'description': text_data.get('description', ''),
                'unformatted_text': text_data.get('unformatted_text', ''),
            }
            
            obj, created = BotText.objects.update_or_create(
                text_name=text_name,
                defaults=defaults
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

        return Response({
            'created': created_count,
            'updated': updated_count,
            'total': created_count + updated_count
        })


@method_decorator(staff_member_required, name='dispatch')
class BulkQuestionImportView(View):
    """
    View для массовой загрузки вопросов из XLSX файла.
    Доступен только администраторам.
    """
    
    def get(self, request):
        """Отображение формы загрузки"""
        return render(request, 'main/bulk_question_import.html')
    
    def post(self, request):
        """Обработка загруженного файла"""
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'Файл не загружен'}, status=400)
        
        file = request.FILES['file']
        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'error': 'Поддерживаются только XLSX/XLS файлы'}, status=400)
        
        try:
            # Читаем Excel файл
            df = pd.read_excel(file, engine='openpyxl')
            
            results = self._process_excel_data(df)
            return JsonResponse(results)
            
        except Exception as e:
            return JsonResponse({'error': f'Ошибка обработки файла: {str(e)}'}, status=500)
    
    def _process_excel_data(self, df):
        """Обработка данных из Excel"""
        created_questions = 0
        created_topics = 0
        created_answers = 0
        errors = []
        
        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Пропускаем пустые строки
                    if pd.isna(row['text']) or not str(row['text']).strip():
                        continue
                    
                    # Обрабатываем сложность
                    difficulty = self._parse_difficulty(row['difficulty'])
                    
                    # Создаем или получаем тему
                    topic = None
                    if not pd.isna(row['theme']) and str(row['theme']).strip():
                        topic_name = str(row['theme']).strip()
                        topic, topic_created = Topic.objects.get_or_create(
                            name=topic_name,
                            defaults={'description': f'Тема: {topic_name}'}
                        )
                        if topic_created:
                            created_topics += 1
                    
                    # Собираем ответы
                    answers = []
                    for i in range(1, 5):  # answer_1, answer_2, answer_3, answer_4
                        answer_text = row[f'answer{i}']
                        if not pd.isna(answer_text) and str(answer_text).strip():
                            answers.append(str(answer_text).strip())
                    
                    # Определяем тип вопроса
                    question_type = Question.QuestionTypeChoices.VARIANT if len(answers) > 1 else Question.QuestionTypeChoices.TEXT
                    
                    # Создаем вопрос
                    question_data = {
                        'text': str(row['text']).strip(),
                        'difficulty': difficulty,
                        'game_use_type': Question.QuestionUseTypeChoices.DM,
                        'comment': str(row['comment']).strip() if not pd.isna(row['comment']) else None,
                        'question_type': question_type,
                    }
                    
                    # Проверяем на дублирование по хешу (если есть)
                    if not pd.isna(row['hash']):
                        question_hash = str(row['hash']).strip()
                        # Можно добавить логику проверки дублирования
                    
                    question = Question.objects.create(**question_data)
                    created_questions += 1
                    
                    # Связываем с темой
                    if topic:
                        question.topics.add(topic)
                    
                    # Создаем ответы
                    if question_type == Question.QuestionTypeChoices.TEXT:
                        # Для текстовых вопросов создаем один правильный ответ
                        correct_answer_text = str(row['right_answer']).strip() if not pd.isna(row['right_answer']) else answers[0] if answers else ""
                        if correct_answer_text:
                            QuestionAnswer.objects.create(
                                question=question,
                                text=correct_answer_text,
                                is_right=True
                            )
                            created_answers += 1
                    else:
                        # Для вопросов с вариантами создаем все ответы
                        correct_index = None
                        if not pd.isna(row['q_index']):
                            try:
                                correct_index = int(row['q_index'])
                            except (ValueError, TypeError):
                                pass
                        
                        # Если индекс не указан, пытаемся найти правильный ответ по тексту
                        if correct_index is None and not pd.isna(row['right_answer']):
                            correct_answer_text = str(row['right_answer']).strip()
                            for i, answer in enumerate(answers):
                                if answer == correct_answer_text:
                                    correct_index = i
                                    break
                        
                        # Создаем все ответы
                        for i, answer_text in enumerate(answers):
                            is_correct = (correct_index is not None and i == correct_index)
                            QuestionAnswer.objects.create(
                                question=question,
                                text=answer_text,
                                is_right=is_correct
                            )
                            created_answers += 1
                    
                except Exception as e:
                    errors.append(f'Строка {index + 2}: {str(e)}')
                    continue
        
        return {
            'success': True,
            'created_questions': created_questions,
            'created_topics': created_topics, 
            'created_answers': created_answers,
            'errors': errors,
            'total_processed': len(df)
        }
    
    def _parse_difficulty(self, difficulty_text):
        """Преобразование текста сложности в число"""
        if pd.isna(difficulty_text):
            return 1
        
        difficulty_str = str(difficulty_text).lower().strip()
        difficulty_map = {
            'легко': 1,
            'легкий': 1,
            'легкая': 1,
            'easy': 1,
            'средне': 2,
            'средний': 2,
            'средняя': 2,
            'medium': 2,
            'сложно': 3,
            'сложный': 3,
            'сложная': 3,
            'hard': 3,
            'сложнее': 4,
            'очень сложно': 5,
            'очень сложный': 5,
        }
        
        return difficulty_map.get(difficulty_str, 1)


class QuestionLikeView(APIView):
    """
    API для добавления лайка к вопросу
    """
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [PlayerTokenAuthentication]
    
    def post(self, request, question_id):
        try:
            # Атомарное увеличение лайков на уровне БД
            updated_count = Question.objects.filter(id=question_id).update(likes=F('likes') + 1)
            
            if updated_count == 0:
                return Response({'error': 'Вопрос не найден'}, status=status.HTTP_404_NOT_FOUND)
            
            # Получаем обновленные значения
            question = Question.objects.get(id=question_id)
            return Response({
                'success': True,
                'likes': question.likes,
                'dislikes': question.dislikes
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class QuestionDislikeView(APIView):
    """
    API для добавления дизлайка к вопросу
    """
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [PlayerTokenAuthentication]
    
    def post(self, request, question_id):
        try:
            # Атомарное увеличение дизлайков на уровне БД
            updated_count = Question.objects.filter(id=question_id).update(dislikes=F('dislikes') + 1)
            
            if updated_count == 0:
                return Response({'error': 'Вопрос не найден'}, status=status.HTTP_404_NOT_FOUND)
            
            # Получаем обновленные значения
            question = Question.objects.get(id=question_id)
            return Response({
                'success': True,
                'likes': question.likes,
                'dislikes': question.dislikes
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
