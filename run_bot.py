# run_bot.py
import asyncio
from telegram_handler import TelegramBotHandler

def main_bot(bot_queue):
    token = "8113099910:AAHmDzRmlYuDzIPPXSD5lY1IuM0NFsCBJtQ"
    bot_handler = TelegramBotHandler(token, bot_queue)
    asyncio.run(bot_handler.run_bot())
