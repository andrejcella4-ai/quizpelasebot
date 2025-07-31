import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import router as solo_router
from team_handlers import router as team_router
from dotenv import load_dotenv
import os


load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)

# Use memory storage for FSM and register handlers
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(solo_router)
dp.include_router(team_router)

async def main():
    # Start the bot
    logging.info("Starting bot...")

    # Skip pending updates
    await bot.delete_webhook(drop_pending_updates=True)

    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
