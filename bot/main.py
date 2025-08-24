import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from handlers import router as solo_router
from team_handlers import router as team_router
from dotenv import load_dotenv
from aiohttp import web, web_runner
import os
import json


load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL где будет работать webhook
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")  # Путь для webhook
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "localhost")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", 8080))

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)

# Use memory storage for FSM and register handlers
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(solo_router)
dp.include_router(team_router)

async def setup_webhook(webhook_url: str):
    """Настройка вебхука для бота"""
    try:
        # Удаляем старый вебхук если есть
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Устанавливаем новый вебхук
        result = await bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook установлен: {result}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при установке вебхука: {e}")
        return False


async def delete_webhook():
    """Удаление вебхука"""
    try:
        result = await bot.delete_webhook()
        logging.info(f"Webhook удален: {result}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при удалении вебхука: {e}")
        return False


async def get_webhook_info():
    """Получение информации о вебхуке"""
    try:
        info = await bot.get_webhook_info()
        logging.info(f"Информация о вебхуке: {info}")
        return info
    except Exception as e:
        logging.error(f"Ошибка при получении информации о вебхуке: {e}")
        return None


async def telegram_webhook_handler(request):
    """Прямой обработчик веб-хуков от Telegram"""
    try:
        # Читаем JSON напрямую для максимальной скорости
        update_data = await request.json()
        update = Update(**update_data)
        
        # Обрабатываем обновление через диспетчер
        await dp.feed_update(bot, update)
        
        # Возвращаем минимальный ответ
        return web.Response(text="OK", content_type="text/plain")
    except Exception as e:
        logging.error(f"Ошибка при обработке веб-хука: {e}")
        return web.Response(text="Error", status=500, content_type="text/plain")


async def health_check_handler(request):
    """Health check для мониторинга"""
    return web.Response(text="Bot is running", content_type="text/plain")


async def init_webhook():
    """Инициализация веб-хука"""
    # Создаем веб-приложение с минимальными настройками для максимальной скорости
    app = web.Application(
        client_max_size=1024*1024,  # 1MB max request size
        handler_args={'access_log': None}  # Отключаем access log для скорости
    )
    
    # Основной эндпоинт для Telegram веб-хуков
    app.router.add_post(WEBHOOK_PATH, telegram_webhook_handler)
    
    # Дополнительные эндпоинты
    app.router.add_get('/health', health_check_handler)
    
    # Настраиваем веб-хук в Telegram
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await setup_webhook(webhook_url)
        logging.info(f"Веб-хук настроен на: {webhook_url}")
        logging.info(f"Health check доступен: {WEBHOOK_URL}/health")
    else:
        logging.warning("WEBHOOK_URL не задан в переменных окружения")
    
    return app


async def start_polling():
    """Запуск в режиме polling (для разработки)"""
    logging.info("Запуск бота в режиме polling...")
    await dp.start_polling(bot)


async def start_webhook():
    """Запуск в режиме webhook"""
    logging.info("Запуск бота в режиме webhook...")
    app = await init_webhook()
    
    # Запуск веб-сервера
    runner = web_runner.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    
    logging.info(f"Веб-сервер запущен на {WEBAPP_HOST}:{WEBAPP_PORT}")
    
    # Ждем завершения
    try:
        await asyncio.Future()  # Ждем бесконечно
    except KeyboardInterrupt:
        logging.info("Остановка сервера...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    # Определяем режим работы из переменных окружения
    mode = os.getenv("BOT_MODE", "polling")  # polling или webhook
    
    if mode == "webhook":
        asyncio.run(start_webhook())
    else:
        asyncio.run(start_polling())
