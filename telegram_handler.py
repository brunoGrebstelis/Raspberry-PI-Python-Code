import asyncio
import json
import os
from utils import generate_locker_info
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

CHAT_IDS_FILE = "chats.json"

def load_chat_ids():
    """Load saved chat IDs from JSON file, returning a list of ints."""
    if not os.path.exists(CHAT_IDS_FILE):
        return []
    with open(CHAT_IDS_FILE, "r") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return []
        except json.JSONDecodeError:
            return []

def save_chat_ids(chat_ids):
    """Save a list of chat IDs to JSON file."""
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(chat_ids, f)

class TelegramBotHandler:
    """
    A Telegram bot that:
    1) Records /start chat IDs in a JSON file.
    2) Reads messages from a multiprocessing.Queue
       and sends them to the relevant chats (or all).
    """

    def __init__(self, token: str, bot_queue):
        self.token = token
        self.bot_queue = bot_queue
        self.app = ApplicationBuilder().token(self.token).build()

        # Add some handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("info", self.info_command))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """When user sends /start, store their chat ID in chats.json if not already there."""
        chat_id = update.effective_chat.id
        await update.message.reply_text("✅ Bot is online! I'll notify you of purchases.")
        
        # Load existing chat IDs
        chat_ids = load_chat_ids()
        # Add if missing
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            save_chat_ids(chat_ids)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Just echo the text, for demonstration."""
        text = update.message.text
        await update.message.reply_text(f"You said: {text}")


    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Respond to /info by showing locker prices from lockers.json.
        """
        info_text = generate_locker_info()   # calls the function in utils.py
        await update.message.reply_text(info_text)


    async def run_bot(self):
        """
        1) Initialize and start the bot
        2) Start polling
        3) Start a background task to read from queue
        4) Keep running until the process is stopped
        5) On exit, stop & shutdown
        """
        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            # Start reading from the queue in a background task
            queue_task = asyncio.create_task(self.read_queue_loop())

            # Keep running until the process is stopped
            await queue_task

        except Exception as e:
            print(f"[TelegramBotHandler] Caught exception: {e}")

        finally:
            print("[TelegramBotHandler] Stopping updater ...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            print("[TelegramBotHandler] Bot shutdown complete.")
            

    async def read_queue_loop(self):
        """
        Continuously read messages from the multiprocessing.Queue.
        If 'chat_id' is None, broadcast to ALL saved IDs.
        If 'chat_id' is an integer, send only to that one chat.
        """
        while True:
            msg = await asyncio.to_thread(self.bot_queue.get)

            # If the message is None, stop the bot
            if msg is None:
                print("[TelegramBotHandler] Received stop signal from queue.")
                break

            # Expecting a dict like { "chat_id": ..., "text": ... }
            chat_id = msg.get("chat_id")
            text = msg.get("text", "No text found")

            # Send the message
            if chat_id is None:
                all_chat_ids = load_chat_ids()
                if not all_chat_ids:
                    print("[TelegramBotHandler] No chat IDs found. Skipping broadcast.")
                    continue
                for cid in all_chat_ids:
                    await self._send_message_with_retries(cid, text)
            else:
                await self._send_message_with_retries(chat_id, text)


    async def _send_message_with_retries(self, chat_id, text, retries=3):
        """
        Send a message to a specific chat ID with retry logic.
        """
        for attempt in range(retries):
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=text)
                print(f"[TelegramBotHandler] Message sent to {chat_id}")
                return
            except Exception as err:
                print(f"[TelegramBotHandler] Attempt {attempt + 1} failed to send to {chat_id}: {err}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"[TelegramBotHandler] Failed to send message to {chat_id} after {retries} attempts.")

