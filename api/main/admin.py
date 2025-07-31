from django.contrib import admin
from .models import TelegramPlayer, Topic, Question, QuestionAnswer, Quiz
from .models import PlayerToken


@admin.register(TelegramPlayer)
class TelegramPlayerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'username', 'telegram_id', 'added_at')
    search_fields = ('first_name', 'last_name', 'username', 'telegram_id')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question_type', 'difficulty')
    list_filter = ('question_type', 'difficulty')
    search_fields = ('text',)

@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_right')
    list_filter = ('is_right',)
    search_fields = ('text',)

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('name', 'quiz_type', 'amount_questions', 'time_to_answer')
    list_filter = ('quiz_type',)
    search_fields = ('name',)

@admin.register(PlayerToken)
class PlayerTokenAdmin(admin.ModelAdmin):
    list_display = ('player', 'key', 'created')
    search_fields = ('player__username', 'key')
