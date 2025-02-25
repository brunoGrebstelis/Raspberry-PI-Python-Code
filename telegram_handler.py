import asyncio
import json
import os
from utils import generate_locker_info, generate_sales_report, generate_csv_file
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
        self.app.add_handler(CommandHandler("csv", self.csv_command))
        self.app.add_handler(CommandHandler("climate", self.climate_command))
        self.app.add_handler(CommandHandler("climate_csv", self.climate_csv_command))
        self.app.add_handler(CommandHandler("help", self.help_command))

        # Inline button handler for the sales selection
        self.app.add_handler(CallbackQueryHandler(self.handle_csv_selection, pattern="^csv_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_climate_csv_selection, pattern="^climate_csv_"))
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

    async def csv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Presents the same time-period options as /sales but will produce a CSV file
        instead of text/charts.
        """
        keyboard = [
            [InlineKeyboardButton("📅 This Year", callback_data="csv_this_year")],
            [InlineKeyboardButton("📆 This Month", callback_data="csv_this_month")],
            [InlineKeyboardButton("📅 Last Year", callback_data="csv_last_year")],
            [InlineKeyboardButton("📆 Last Month", callback_data="csv_last_month")],
            [InlineKeyboardButton("📅 Today", callback_data="csv_today")],
            [InlineKeyboardButton("📆 Yesterday", callback_data="csv_yesterday")],
            [InlineKeyboardButton("📈 Total", callback_data="csv_total")],
            [InlineKeyboardButton("✍️ Manual Entry", callback_data="csv_manual_entry")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._retry(
            update.message.reply_text,
            "Please select a time period for the CSV export:",
            reply_markup=reply_markup,
        )

    async def climate_csv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Presents the same time-period options as /csv, but for climate data instead of sales.
        """
        keyboard = [
            [InlineKeyboardButton("📅 This Year", callback_data="climate_csv_this_year")],
            [InlineKeyboardButton("📆 This Month", callback_data="climate_csv_this_month")],
            [InlineKeyboardButton("📅 Last Year", callback_data="climate_csv_last_year")],
            [InlineKeyboardButton("📆 Last Month", callback_data="climate_csv_last_month")],
            [InlineKeyboardButton("📅 Today", callback_data="climate_csv_today")],
            [InlineKeyboardButton("📆 Yesterday", callback_data="climate_csv_yesterday")],
            [InlineKeyboardButton("📈 Total", callback_data="climate_csv_total")],
            [InlineKeyboardButton("✍️ Manual Entry", callback_data="climate_csv_manual_entry")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._retry(
            update.message.reply_text,
            "Please select a time period for the climate CSV export:",
            reply_markup=reply_markup,
        )


    async def climate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Responds with the latest climate reading and average (today, yesterday, last 30 days),
        or "ND" if no data is found for a particular period.
        Uses emojis for temperature (🌡) and humidity (💧).
        """
        from utils import get_climate_stats
        stats = get_climate_stats()

        # Helper to format a single temperature/humidity line
        def fmt_line(label, t, h):
            # If t or h is None => "ND"
            if t is None or h is None:
                return f"{label}: ND"
            return f"{label}: 🌡{t:.1f}°C | 💧{h:.1f}%"

        # Build the lines
        lines = []
        lines.append(fmt_line("Current", stats["current_temp"], stats["current_hum"]))
        lines.append(fmt_line("Today", stats["avg_today_temp"], stats["avg_today_hum"]))
        lines.append(fmt_line("Yesterday", stats["avg_yesterday_temp"], stats["avg_yesterday_hum"]))
        lines.append(fmt_line("Last 30 days", stats["avg_30days_temp"], stats["avg_30days_hum"]))
        

        msg_text = "\n".join(lines)

        # Send it back
        await self._retry(update.message.reply_text, msg_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Sends a list of available commands with brief descriptions (with emojis).
        """
        print("[DEBUG] help_command triggered")
        help_text = (
            "🌐Bot Commands Help\n\n"
            "/start - 🤖Confirm the bot is online\n"
            "/info - ℹDisplay locker info/status\n"
            "/sales - 💰Generate sales reports\n"
            "/csv - 📊Generate sales CSV files\n"
            "/climate - 🌡️Show climate readings\n"
            "/climate_csv - 🌦️Generate climate CSV files\n"
            "/help - ❓Show this help message\n"
        )

        await self._retry(update.message.reply_text, help_text)



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



    async def handle_csv_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle inline keyboard callbacks for CSV export.
        """
        query = update.callback_query
        await query.answer()
        data = query.data

        # Predefined quick picks
        if data in [
            "csv_this_year",
            "csv_this_month",
            "csv_last_year",
            "csv_last_month",
            "csv_today",
            "csv_yesterday",
            "csv_total",
        ]:
            # Convert e.g. "csv_this_year" -> "this_year" -> "This Year"
            label = data.replace("csv_", "").replace("_", " ").title()
            await self.send_csv_report(label)

        elif data == "csv_manual_entry":
            # Switch to manual entry steps
            context.user_data["csv_step"] = "start_date"
            await self._retry(
                query.edit_message_text,
                "Please enter the start date (YYYY-MM-DD) for CSV export:",
            )


    async def handle_climate_csv_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle inline keyboard callbacks for climate CSV export.
        """
        query = update.callback_query
        await query.answer()
        data = query.data

        # For direct picks
        if data in [
            "climate_csv_this_year",
            "climate_csv_this_month",
            "climate_csv_last_year",
            "climate_csv_last_month",
            "climate_csv_today",
            "climate_csv_yesterday",
            "climate_csv_total",
        ]:
            # e.g. "climate_csv_this_year" => "this_year" => "This Year"
            label = data.replace("climate_csv_", "").replace("_", " ").title()
            await self.send_climate_csv_report(label)

        elif data == "climate_csv_manual_entry":
            context.user_data["climate_csv_step"] = "start_date"
            await self._retry(
                query.edit_message_text,
                "Please enter the start date (YYYY-MM-DD) for climate CSV export:",
            )



    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Single text handler that:
        - If user_data indicates a /climate_csv manual entry, handle it.
        - Else if user_data indicates a /csv manual entry, handle it.
        - Else if user_data indicates a /sales manual entry, handle it.
        - Otherwise, fallback and just echo.
        """

        # 1) Handle /climate_csv manual entry flow.
        if "climate_csv_step" in context.user_data:
            step = context.user_data["climate_csv_step"]

            if step == "start_date":
                context.user_data["climate_csv_start"] = update.message.text
                context.user_data["climate_csv_step"] = "end_date"
                await self._retry(
                    update.message.reply_text,
                    "Please enter the end date (YYYY-MM-DD) for climate CSV export:"
                )
                return  # Stop here

            elif step == "end_date":
                context.user_data["climate_csv_end"] = update.message.text
                start_date = context.user_data["climate_csv_start"]
                end_date   = context.user_data["climate_csv_end"]
                period_label = f"{start_date} to {end_date}"

                # Generate/send the climate CSV for that range
                await self.send_climate_csv_report(period_label)

                # Clear state so we exit the climate CSV flow
                context.user_data.clear()
                return

        # 2) Handle /csv manual entry flow (sales CSV).
        if "csv_step" in context.user_data:
            step = context.user_data["csv_step"]

            if step == "start_date":
                context.user_data["csv_start_date"] = update.message.text
                context.user_data["csv_step"] = "end_date"
                await self._retry(
                    update.message.reply_text,
                    "Please enter the end date (YYYY-MM-DD) for CSV export:"
                )
                return  # Stop here so we don't fall through to sales logic.

            elif step == "end_date":
                context.user_data["csv_end_date"] = update.message.text
                start_date = context.user_data["csv_start_date"]
                end_date   = context.user_data["csv_end_date"]
                period_label = f"{start_date} to {end_date}"

                # Generate/send the sales CSV for the selected range
                await self.send_csv_report(period_label)

                # Clear state so we exit the CSV flow
                context.user_data.clear()
                return

        # 3) Handle /sales manual entry flow.
        if "sales_step" in context.user_data:
            step = context.user_data["sales_step"]

            if step == "start_date":
                context.user_data["start_date"] = update.message.text
                context.user_data["sales_step"] = "end_date"
                await self._retry(
                    update.message.reply_text,
                    "Please enter the end date (YYYY-MM-DD):"
                )
                return

            elif step == "end_date":
                context.user_data["end_date"] = update.message.text
                start_date = context.user_data["start_date"]
                end_date   = context.user_data["end_date"]
                period_label = f"{start_date} to {end_date}"

                # Generate/send the sales report for that range
                await self.sales(period_label)

                # Clear state so we exit the sales flow
                context.user_data.clear()
                return

        # 4) Fallback if no manual entry is in progress.
        await self._retry(
            #update.message.reply_text,
            #f"You said: {update.message.text}"
        )


    async def sales(self, period: str):
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[sales] No chat IDs found. Nobody to send the sales report to.")
            return

        # 1) Let utils.py do the heavy lifting
        report_text, line_chart_path, pie_chart_path = generate_sales_report(period)

        # 2) Send the results to each chat
        for cid in all_chat_ids:
            # Send the text
            await self._send_message_with_retries(cid, report_text)

            # Send line chart if generated
            if line_chart_path and os.path.isfile(line_chart_path):
                await self._send_photo_with_retries(cid, line_chart_path, caption="Sales Over Time")

            # Send pie chart if generated
            if pie_chart_path and os.path.isfile(pie_chart_path):
                await self._send_photo_with_retries(cid, pie_chart_path, caption="Best Selling Lockers")

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
                

    async def _send_photo_with_retries(self, chat_id, image_path, caption="", retries=5):
        """
        Send a photo to a specific chat ID with retry logic.
        The first retry is faster to improve success rate.
        """
        for attempt in range(retries):
            try:
                with open(image_path, "rb") as f:
                    await self.app.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
                print(f"[TelegramBotHandler] Photo sent to {chat_id}")
                return
            except TimedOut as e:
                print(f"Attempt {attempt + 1} failed (TimedOut) to send photo to {chat_id}: {e}")
                if attempt < retries - 1:
                    if attempt == 0:
                        await asyncio.sleep(0.5)  # fast retry
                    else:
                        await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[TelegramBotHandler] Failed to send photo to {chat_id} after {retries} attempts.")
                    return
            except BadRequest as e:
                print(f"[TelegramBotHandler] BadRequest (photo) to {chat_id}: {e}")
                return
            except Exception as e:
                print(f"[TelegramBotHandler] Attempt {attempt + 1} failed (Other Error) to send photo to {chat_id}: {e}")
                if attempt < retries - 1:
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                    else:
                        await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[TelegramBotHandler] Failed to send photo to {chat_id} after {retries} attempts.")
                    return
                

    async def send_csv_report(self, period: str):
        """
        Generate a CSV for the specified period and broadcast it to all known chat IDs.
        """
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[send_csv_report] No chat IDs found. Nobody to send CSV to.")
            return

        from utils import generate_csv_file
        csv_path = generate_csv_file(period)

        # Debug printing:
        print(f"[send_csv_report] generate_csv_file returned: {csv_path}")

        if not csv_path:
            # Means parse failure or no rows
            msg_text = f"No CSV data found for period: {period}"
            for cid in all_chat_ids:
                await self._send_message_with_retries(cid, msg_text)
            return

        # We have a CSV file -> broadcast it
        for cid in all_chat_ids:
            await self._send_document_with_retries(cid, csv_path, caption=f"CSV Data for {period}")


    async def send_climate_csv_report(self, period: str):
        """
        Generate a climate CSV for the specified period and broadcast to all known chat IDs.
        """
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[send_climate_csv_report] No chat IDs found. Nobody to send climate CSV to.")
            return

        from utils import generate_climate_csv_file
        csv_path = generate_climate_csv_file(period)
        print(f"[send_climate_csv_report] generate_climate_csv_file returned: {csv_path}")

        if not csv_path:
            msg_text = f"No climate CSV data found for period: {period}"
            for cid in all_chat_ids:
                await self._send_message_with_retries(cid, msg_text)
            return

        for cid in all_chat_ids:
            await self._send_document_with_retries(cid, csv_path, caption=f"Climate CSV Data for {period}")



    async def _send_document_with_retries(self, chat_id, file_path, caption="", retries=5):
        """
        Send a document (e.g. CSV file) to a specific chat ID with retry logic.
        """
        for attempt in range(retries):
            try:
                with open(file_path, "rb") as doc:
                    await self.app.bot.send_document(chat_id=chat_id, document=doc, caption=caption)
                print(f"[TelegramBotHandler] Document sent to {chat_id}")
                return
            except TimedOut as e:
                print(f"Attempt {attempt + 1} failed (TimedOut) sending document to {chat_id}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"[TelegramBotHandler] Failed to send document after {retries} attempts.")
                    return
            except BadRequest as e:
                print(f"[TelegramBotHandler] BadRequest (document) to {chat_id}: {e}")
                return
            except Exception as e:
                print(f"[TelegramBotHandler] Attempt {attempt + 1} failed (Other Error) sending document: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    print(f"[TelegramBotHandler] Failed to send document after {retries} attempts.")
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

        Now also checks for 'image_path' to send an image instead of text.
        """
        while True:
            msg = await asyncio.to_thread(self.bot_queue.get)

            # If the message is None, stop the bot
            if msg is None:
                print("[TelegramBotHandler] Received stop signal from queue.")
                break

            chat_id = msg.get("chat_id")  # Could be None (broadcast) or a specific chat_id

            # Check if this is an image message
            if "image_path" in msg:
                image_path = msg["image_path"]
                caption = msg.get("caption", "")  # optional
                # Send the photo with retries
                await self._send_photo_with_retries(chat_id, image_path, caption)
            else:
                # Otherwise, assume it's a text message
                text = msg.get("text", "No text found")
                # If chat_id is None, broadcast to all saved IDs
                if chat_id is None:
                    all_chat_ids = load_chat_ids()
                    if not all_chat_ids:
                        print("[TelegramBotHandler] No chat IDs found. Skipping broadcast.")
                        continue
                    for cid in all_chat_ids:
                        await self._send_message_with_retries(cid, text)
                else:
                    # Send only to the specified chat_id
                    await self._send_message_with_retries(chat_id, text)
