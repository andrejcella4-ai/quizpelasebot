from django.db.models.signals import post_save
from django.dispatch import receiver
import asyncio
import os

from aiogram import Bot

from .models import PlanTeamQuiz, Team, BotText


@receiver(post_save, sender=PlanTeamQuiz)
def on_plan_team_quiz_created(sender, instance: PlanTeamQuiz, created: bool, **kwargs):
    if not created:
        return
    
    # Проверяем, нужно ли отправлять уведомления
    if not instance.send_notification:
        return
    
    # Ищем текст уведомления в BotTexts
    try:
        bot_text = BotText.objects.get(text_name='team_quiz_notification')
        text = bot_text.unformatted_text
    except BotText.DoesNotExist:
        # Если текст не найден, используем дефолтный
        text = (
            "📢 Новая командная викторина уже доступна!\n\n"
            "Сегодня вас ждёт 6 свежих вопросов — обсудите, подумайте и ответьте как единое целое! 🧠⚡️"
        )
    
    # Получаем список chat_username всех команд
    team_chats = list(Team.objects.values_list('chat_username', flat=True))
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or not team_chats:
        return

    async def _broadcast():
        bot = Bot(token=bot_token)
        try:
            for chat_username in team_chats:
                try:
                    # Отправляем в чат команды (chat_username может быть @username или chat_id)
                    if chat_username.startswith('@'):
                        await bot.send_message(chat_username, text, parse_mode='Markdown')
                    else:
                        # Если это не username, возможно это chat_id
                        try:
                            chat_id = int(chat_username)
                            await bot.send_message(chat_id, text, parse_mode='Markdown')
                        except ValueError:
                            # Если не удалось преобразовать в int, пробуем как username
                            await bot.send_message(f"@{chat_username}", text, parse_mode='Markdown')
                except Exception as e:
                    print(f"Ошибка отправки уведомления в чат {chat_username}: {e}")
                    continue
        finally:
            await bot.session.close()

    try:
        asyncio.create_task(_broadcast())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_broadcast())

