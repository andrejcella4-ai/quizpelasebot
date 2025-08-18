from django.db.models.signals import post_save
from django.dispatch import receiver
import asyncio
import os

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .models import PlanTeamQuiz, TelegramPlayer


@receiver(post_save, sender=PlanTeamQuiz)
def on_plan_team_quiz_created(sender, instance: PlanTeamQuiz, created: bool, **kwargs):
    if not created:
        return
    # Текст уведомления
    text = (
        "📢 Новая командная викторина уже доступна!\n\n"
        "Сегодня вас ждёт 6 свежих вопросов — обсудите, подумайте и ответьте как единое целое! 🧠⚡️"
    )
    # Кнопка «Не напоминать»
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text='🔕 Не напоминать', callback_data='notify:mute')]]
    )

    # Получаем список id пользователей с включенными уведомлениями
    chat_ids = list(TelegramPlayer.objects.filter(notification_is_on=True).values_list('telegram_id', flat=True))
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        return

    async def _broadcast():
        bot = Bot(token=bot_token)
        try:
            for chat_id in chat_ids:
                try:
                    await bot.send_message(chat_id, text, reply_markup=kb)
                except Exception:
                    continue
        finally:
            await bot.session.close()

    try:
        asyncio.create_task(_broadcast())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_broadcast())

