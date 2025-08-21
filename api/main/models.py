from django.db import models

import binascii
import os


class Team(models.Model):
    name = models.CharField(max_length=255, verbose_name='Название команды')
    captain = models.ForeignKey('TelegramPlayer', on_delete=models.CASCADE, verbose_name='Капитан')
    chat_username = models.CharField(max_length=255, verbose_name='Telegram username чата', unique=True)
    total_scores = models.PositiveIntegerField(default=0, verbose_name='Общий счет')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Команда'
        verbose_name_plural = 'Команды'


class TelegramPlayer(models.Model):
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Фамилия')
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name='Имя пользователя')
    phone = models.CharField(max_length=255, blank=True, null=True, verbose_name='Телефон')
    telegram_id = models.BigIntegerField(unique=True, verbose_name='Telegram ID')
    lang_code = models.CharField(max_length=255, blank=True, null=True, verbose_name='Язык')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    total_xp = models.PositiveIntegerField(default=0, verbose_name='Общий XP')
    notification_is_on = models.BooleanField(default=True, verbose_name='Уведомления включены')
    last_played_at = models.DateTimeField(blank=True, null=True, verbose_name='Последняя игра')
    current_streak = models.PositiveIntegerField(default=0, verbose_name='Текущий стрик (дней)')

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.username}"

    @property
    def is_authenticated(self) -> bool:
        return True

    class Meta:
        verbose_name = 'Игрок'
        verbose_name_plural = 'Игроки'


class Topic(models.Model):
    name = models.CharField(max_length=255, verbose_name='Название темы')
    description = models.TextField(verbose_name='Описание темы')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тема'
        verbose_name_plural = 'Темы'


class Question(models.Model):

    class QuestionTypeChoices(models.TextChoices):
        TEXT = 'text', 'Text'
        VARIANT = 'variant', 'Variant'

    text = models.TextField(verbose_name='Текст вопроса')
    question_type = models.CharField(max_length=255, choices=QuestionTypeChoices.choices, verbose_name='Тип вопроса')
    difficulty = models.PositiveSmallIntegerField(default=1, verbose_name='Сложность') # from 1 to 5
    topics = models.ManyToManyField(Topic, related_name='questions', verbose_name='Темы')
    comment = models.TextField(blank=True, null=True, verbose_name='Комментарий')

    likes = models.PositiveIntegerField(default=0, verbose_name='Лайки')
    dislikes = models.PositiveIntegerField(default=0, verbose_name='Дизлайки')

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'


class QuestionAnswer(models.Model):
    text = models.TextField(verbose_name='Текст ответа')
    is_right = models.BooleanField(default=False, verbose_name='Правильный ответ')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, verbose_name='Вопрос')

    def __str__(self):
        return self.text

    class Meta:
        verbose_name = 'Ответ на вопрос'
        verbose_name_plural = 'Ответы на вопросы'


class Quiz(models.Model):

    class QuizTypeChoices(models.TextChoices):
        TEAM = 'team', 'TM'
        SINGLE = 'solo', 'SL'
        DM = 'dm', 'DM'

    name = models.CharField(max_length=255, verbose_name='Название викторины')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    quiz_type = models.CharField(max_length=255, choices=QuizTypeChoices.choices, verbose_name='Тип викторины')
    amount_questions = models.PositiveSmallIntegerField(default=10, verbose_name='Количество вопросов')
    time_to_answer = models.PositiveSmallIntegerField(default=10, verbose_name='Время на ответ')
    questions = models.ManyToManyField('Question', related_name='quizzes', verbose_name='Вопросы')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Квиз'
        verbose_name_plural = 'Квизы'


class PlanTeamQuiz(models.Model):
    quiz = models.ForeignKey('Quiz', on_delete=models.CASCADE, related_name='planned_team_quizzes', verbose_name='Квиз')
    scheduled_datetime = models.DateTimeField(verbose_name='Время проведения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    def __str__(self):
        return f"{self.quiz.name} @ {self.scheduled_datetime.isoformat()}"

    class Meta:
        verbose_name = 'Запланированная командная игра'
        verbose_name_plural = 'Запланированные командные игры'

# Custom token model for DRF
class PlayerToken(models.Model):
    key = models.CharField(max_length=40, primary_key=True, verbose_name='Токен')
    player = models.OneToOneField(TelegramPlayer, related_name='auth_token', on_delete=models.CASCADE, verbose_name='Игрок')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = binascii.hexlify(os.urandom(20)).decode()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Токен игрока'
        verbose_name_plural = 'Токены игроков'
