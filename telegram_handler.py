import asyncio
import json
import os
from utils import generate_locker_info
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
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
    2) Provides /info, /sales, and more.
    3) Reads messages from a multiprocessing.Queue
       and sends them to the relevant chats (or all).
    """

    def __init__(self, token: str, bot_queue):
        self.token = token
        self.bot_queue = bot_queue

        # Build the application (bot)
        self.app = ApplicationBuilder().token(self.token).build()

        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("info", self.info_command))
        self.app.add_handler(CommandHandler("sales", self.sales_command))

        # Inline button handler for the sales selection
        self.app.add_handler(CallbackQueryHandler(self.handle_sales_selection))

        # Single text handler to process manual entry or fallback
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Register a new chat ID and confirm the bot is online."""
        chat_id = update.effective_chat.id
        await self._retry(
            update.message.reply_text,
            "✅ Bot is online! I'll notify you of purchases."
        )

        # Load existing chat IDs
        chat_ids = load_chat_ids()
        # Add if missing
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            save_chat_ids(chat_ids)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Example command that calls a function to generate info."""
        info_text = generate_locker_info()  # from utils.py, adjust as needed
        await self._retry(update.message.reply_text, info_text)

    async def sales_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Presents an inline keyboard with multiple time-period options:
        - This Year, This Month, Last Year, Last Month, Today, Yesterday, Total, Manual Entry
        """
        keyboard = [
            [InlineKeyboardButton("📅 This Year", callback_data="this_year")],
            [InlineKeyboardButton("📆 This Month", callback_data="this_month")],
            [InlineKeyboardButton("📅 Last Year", callback_data="last_year")],
            [InlineKeyboardButton("📆 Last Month", callback_data="last_month")],
            [InlineKeyboardButton("📅 Today", callback_data="today")],
            [InlineKeyboardButton("📆 Yesterday", callback_data="yesterday")],
            [InlineKeyboardButton("📈 Total", callback_data="total")],
            [InlineKeyboardButton("✍️ Manual Entry", callback_data="manual_entry")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._retry(
            update.message.reply_text,
            "Please select a time period for the sales report:",
            reply_markup=reply_markup,
        )

    async def handle_sales_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks for the sales periods."""
        query = update.callback_query
        await query.answer()  # Acknowledge the callback

        data = query.data

        # Direct, predefined time periods
        if data in [
            "this_year",
            "this_month",
            "last_year",
            "last_month",
            "today",
            "yesterday",
            "total",
        ]:
    
            # Then broadcast the final message to all chat IDs
            # (e.g. "This Year", "Last Year", etc.)
            # We'll do a little label cleanup:
            label = data.replace("_", " ").title()
            await self.sales(label)

        elif data == "manual_entry":
            # Switch to manual entry
            context.user_data["sales_step"] = "start_date"
            # Edit the message to prompt for start date
            await self._retry(
                query.edit_message_text,
                "Please enter the start date (YYYY-MM-DD):"
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Single text handler:
          - If user_data indicates manual entry for sales, handle it
          - Otherwise, fallback: echo
        """
        if "sales_step" not in context.user_data:
            # No manual entry in progress => fallback
            await update.message.reply_text(f"You said: {update.message.text}")
            return

        # We are in the manual flow for sales
        step = context.user_data["sales_step"]
        if step == "start_date":
            # Store the start date
            context.user_data["start_date"] = update.message.text
            # Move on to end date
            context.user_data["sales_step"] = "end_date"
            await self._retry(
                update.message.reply_text,
                "Please enter the end date (YYYY-MM-DD):"
            )

        elif step == "end_date":
            # Now we have both dates
            context.user_data["end_date"] = update.message.text
            start_date = context.user_data["start_date"]
            end_date = context.user_data["end_date"]

            # Broadcast "start_date to end_date" to all saved chats
            period_label = f"{start_date} to {end_date}"
            await self.sales(period_label)

            # Clear user_data to exit the manual entry flow
            context.user_data.clear()

    async def sales(self, period: str):
        """
        Broadcast the given sales period message to all chat IDs 
        stored in chats.json.
        """
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[sales] No chat IDs found. Nobody to send the sales report to.")
            return

        text = f"📊 Sales report for: {period}"
        for cid in all_chat_ids:
            await self._send_message_with_retries(cid, text)

    async def _retry(self, func, *args, retries=5, **kwargs):
        """
        Helper function to retry a Telegram API call in case of TimedOut.
        """
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except TimedOut as e:
                print(f"Attempt {attempt + 1} failed (TimedOut): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
            except BadRequest as e:
                # If it's a chat not found, we'll just print and stop trying
                print(f"BadRequest: {e}")
                return
            except Exception as e:
                print(f"Attempt {attempt + 1} failed (Other Error): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def _send_message_with_retries(self, chat_id, text, retries=5):
        """
        Send a message to a specific chat ID with retry logic.
        The first retry is faster to improve success rate.
        """
        for attempt in range(retries):
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=text)
                print(f"[TelegramBotHandler] Message sent to {chat_id}")
                return
            except TimedOut as e:
                print(f"Attempt {attempt + 1} failed (TimedOut) to send to {chat_id}: {e}")
                if attempt < retries - 1:
                    if attempt == 0:
                        await asyncio.sleep(0.5)  # fast retry
                    else:
                        await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[TelegramBotHandler] Failed to send message to {chat_id} after {retries} attempts.")
                    return
            except BadRequest as e:
                print(f"[TelegramBotHandler] BadRequest to {chat_id}: {e}")
                return
            except Exception as e:
                print(f"[TelegramBotHandler] Attempt {attempt + 1} failed to send to {chat_id}: {e}")
                if attempt < retries - 1:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                    else:
                        await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[TelegramBotHandler] Failed to send message to {chat_id} after {retries} attempts.")
                    return

    async def run_bot(self):
        """
        1) Initialize and start the bot.
        2) Start polling.
        3) Start a background task to read from the queue.
        4) Keep running until the process is stopped.
        5) Ensure a graceful shutdown on exit.
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
            print("[TelegramBotHandler] Stopping updater...")
            try:
                await self.app.updater.stop()
                await self.app.stop()
                print("[TelegramBotHandler] Bot shutdown complete.")
            except TimedOut:
                print("[TelegramBotHandler] Timed out during shutdown, suppressing error.")

    async def stop_bot(self):
        """Custom stop method to suppress the 'get_updates' error during shutdown."""
        try:
            print("[TelegramBotHandler] Stopping bot gracefully...")
            await self.app.stop()
        except TimedOut:
            print("[TelegramBotHandler] Suppressing TimedOut error during shutdown.")

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

            if chat_id is None:
                all_chat_ids = load_chat_ids()
                if not all_chat_ids:
                    print("[TelegramBotHandler] No chat IDs found. Skipping broadcast.")
                    continue
                for cid in all_chat_ids:
                    await self._send_message_with_retries(cid, text)
            else:
                await self._send_message_with_retries(chat_id, text)
