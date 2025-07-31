from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
import random

from .models import TelegramPlayer, Quiz, Question, PlayerToken
from .serializers import AuthPlayerSerializer, QuizInfoSerializer, QuestionListSerializer
from .authentication import PlayerTokenAuthentication


class AuthPlayerView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AuthPlayerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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


class QuizSingleView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        quiz_id = request.query_params.get('quiz_id')

        if not quiz_id:
            quiz = Quiz.objects.filter(quiz_type=Quiz.QuizTypeChoices.SINGLE).first()
        else:
            quiz = Quiz.objects.filter(id=quiz_id).first()

        if not quiz:
            return Response({'detail': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = QuizInfoSerializer(quiz)
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
        serializer = QuestionListSerializer(selected, many=True)

        return Response(serializer.data)
