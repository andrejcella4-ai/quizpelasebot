from rest_framework import serializers
from .models import TelegramPlayer, Quiz, Question


class AuthPlayerSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
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

    class Meta:
        model = Question
        fields = ('id', 'text', 'question_type', 'wrong_answers', 'correct_answer')

    def get_wrong_answers(self, obj):
        return list(obj.questionanswer_set.filter(is_right=False).values_list('text', flat=True))

    def get_correct_answer(self, obj):
        ans = obj.questionanswer_set.filter(is_right=True).first()
        return ans.text if ans else ''
