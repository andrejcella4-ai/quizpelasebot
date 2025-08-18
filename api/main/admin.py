from django.contrib import admin

from .models import TelegramPlayer, Topic, Question, QuestionAnswer, Quiz, Team, PlanTeamQuiz, PlayerToken


@admin.register(TelegramPlayer)
class TelegramPlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'username', 'telegram_id', 'added_at', 'total_xp', 'current_streak', 'notification_is_on')
    search_fields = ('first_name', 'last_name', 'username', 'telegram_id')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'question_type', 'difficulty')
    list_filter = ('question_type', 'difficulty')
    search_fields = ('text',)


@admin.register(QuestionAnswer)
class QuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'question', 'is_right')
    list_filter = ('is_right',)
    search_fields = ('text',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'quiz_type', 'amount_questions', 'time_to_answer')
    list_filter = ('quiz_type',)
    search_fields = ('name',)


@admin.register(PlayerToken)
class PlayerTokenAdmin(admin.ModelAdmin):
    list_display = ('player', 'key', 'created')
    search_fields = ('player__username', 'key')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'captain', 'total_scores')
    search_fields = ('name',)


@admin.register(PlanTeamQuiz)
class PlanTeamQuizAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'scheduled_date', 'created_at')
    list_filter = ('scheduled_date',)
