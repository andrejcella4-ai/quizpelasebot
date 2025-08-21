from rest_framework import serializers
from .models import Quiz, Question, Team, TelegramPlayer, PlanTeamQuiz


class AuthPlayerSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    username = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    lang_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class QuizInfoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Quiz
        fields = ('id', 'name', 'description', 'quiz_type', 'amount_questions', 'time_to_answer')


class QuestionListSerializer(serializers.ModelSerializer):
    wrong_answers = serializers.SerializerMethodField()
    correct_answer = serializers.SerializerMethodField()
    time_to_answer = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ('id', 'text', 'question_type', 'wrong_answers', 'correct_answer', 'time_to_answer')

    def get_wrong_answers(self, obj):
        return list(obj.questionanswer_set.filter(is_right=False).values_list('text', flat=True))

    def get_correct_answer(self, obj):
        ans = obj.questionanswer_set.filter(is_right=True).first()
        return ans.text if ans else ''

    def get_time_to_answer(self, obj):
        # Берем из контекста, куда передается значение из связанного Quiz
        value = self.context.get('time_to_answer')
        try:
            return int(value) if value is not None else None
        except Exception:
            return None


class TeamSerializer(serializers.ModelSerializer):
    captain_username = serializers.CharField(source='captain.username', read_only=True)

    class Meta:
        model = Team
        fields = ('id', 'name', 'chat_username', 'captain_username', 'total_scores')
        read_only_fields = ('captain', 'captain_username', 'total_scores')


class PlanTeamQuizSerializer(serializers.ModelSerializer):
    quiz_name = serializers.CharField(source='quiz.name', read_only=True)

    class Meta:
        model = PlanTeamQuiz
        fields = ('id', 'quiz', 'quiz_name', 'scheduled_datetime')


class TelegramPlayerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramPlayer
        fields = ('notification_is_on',)


class LeaderboardEntrySerializer(serializers.Serializer):
    username = serializers.CharField()
    total_xp = serializers.IntegerField()
