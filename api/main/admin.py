from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ManyToManyWidget

from .models import (
    TelegramPlayer,
    Topic,
    Question,
    QuestionAnswer,
    Quiz,
    Team,
    PlanTeamQuiz,
    PlayerToken,
    BotText,
    City,
    QuestionUsage,
    Config
)


@admin.register(QuestionUsage)
class QuestionUsageAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'use_type', 'context_id')
    list_filter = ('use_type', 'context_id')
    search_fields = ('question__text',)


@admin.register(TelegramPlayer)
class TelegramPlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'username', 'telegram_id', 'added_at', 'total_xp', 'current_streak', 'notification_is_on')
    search_fields = ('first_name', 'last_name', 'username', 'telegram_id')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class QuestionAnswerInline(admin.StackedInline):
    model = QuestionAnswer
    extra = 1
    fk_name = 'question'


def make_solo_questions(modeladmin, request, queryset):
    """Перенести выбранные вопросы в режим 'соло'"""
    updated = queryset.update(game_use_type='solo')
    modeladmin.message_user(request, f'Успешно перенесено {updated} вопросов в режим "Соло"')

def make_dm_questions(modeladmin, request, queryset):
    """Перенести выбранные вопросы в режим 'соревновательный'"""
    updated = queryset.update(game_use_type='dm')
    modeladmin.message_user(request, f'Успешно перенесено {updated} вопросов в режим "Соревновательный"')

def clear_game_type(modeladmin, request, queryset):
    """Очистить тип игры для выбранных вопросов"""
    updated = queryset.update(game_use_type=None)
    modeladmin.message_user(request, f'Успешно очищен тип игры для {updated} вопросов')

# Настройка отображаемых названий для действий
make_solo_questions.short_description = "🎮 Перенести в режим 'Соло'"
make_dm_questions.short_description = "⚔️ Перенести в режим 'Соревновательный'"
clear_game_type.short_description = "🔄 Очистить тип игры"


class QuestionResource(resources.ModelResource):
    """Ресурс для импорта/экспорта вопросов"""
    topics = fields.Field(
        column_name='topics',
        attribute='topics',
        widget=ManyToManyWidget(Topic, field='name', separator='|')
    )

    class Meta:
        model = Question
        fields = ('id', 'text', 'difficulty', 'topics', 'comment', 'question_type', 'game_use_type')
        export_order = ('id', 'text', 'difficulty', 'topics', 'comment', 'question_type', 'game_use_type')
        skip_unchanged = True
        report_skipped = True


@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_classes = [QuestionResource]  # Изменено с resource_class на resource_classes
    list_display = ('id', 'text', 'question_type', 'comment', 'difficulty', 'game_use_type', 'image')
    list_filter = ('question_type', 'difficulty', 'game_use_type')
    search_fields = ('text',)

    # Добавляем массовые действия
    actions = [make_solo_questions, make_dm_questions, clear_game_type]

    inlines = [QuestionAnswerInline]


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
    list_display = ('id', 'name', 'chat_username', 'city', 'captain', 'total_scores')
    search_fields = ('name',)


@admin.register(PlanTeamQuiz)
class PlanTeamQuizAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'scheduled_datetime', 'send_notification', 'created_at')
    list_filter = ('scheduled_datetime', 'send_notification')
    fields = ('quiz', 'scheduled_datetime', 'always_active', 'send_notification', 'teams_played')


@admin.register(BotText)
class BotTextAdmin(admin.ModelAdmin):
    list_display = ('id', 'text_name', 'label', 'description', 'unformatted_text')
    search_fields = ('text_name',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'value')
    search_fields = ('name',)
