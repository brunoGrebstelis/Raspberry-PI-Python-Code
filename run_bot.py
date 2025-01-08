# run_bot.py
import asyncio
from telegram_handler import TelegramBotHandler

def main_bot():
    token = "8113099910:AAHmDzRmlYuDzIPPXSD5lY1IuM0NFsCBJtQ"
    bot_handler = TelegramBotHandler(token)

    # Run everything in a single asyncio call
    asyncio.run(bot_handler.run_bot())

if __name__ == "__main__":
    main_bot()
