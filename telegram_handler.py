import asyncio
import json
import os
from datetime import datetime
from utils import generate_locker_info, generate_sales_report, generate_csv_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import TimedOut, BadRequest, NetworkError, RetryAfter  # broadened errors
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
import subprocess
import socket

# ---- Connection profile names (exact, case-sensitive, from `nmcli connection show`) ----
WIFI_CONN_NAME = "WLAN - ZNGQXU"
ETH_CONN_NAME  = "wired connection 1"   # set to "" if you never want Ethernet fallback

CHAT_IDS_FILE = "chats.json"


def log_event(message: str):
    """
    Write each log event in 'logs/BLACK_BOX_Telegram.tx' with date and time, creating
    the logs folder and file if they do not exist.
    """
    if not os.path.exists("logs"):
        os.makedirs("logs")
    with open("logs/BLACK_BOX_Telegram.tx", "a", encoding="utf-8") as f:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"{now_str} {message}\n")


def load_chat_ids():
    """Load saved chat IDs from JSON file, returning a list of ints."""
    log_event("load_chat_ids called")
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
    log_event("save_chat_ids called")
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(chat_ids, f)


class TelegramBotHandler:
    """
    A Telegram bot that:
    1) Records /start chat IDs in a JSON file.
    2) Provides /info, /sales, and more.
    3) Reads messages from a multiprocessing.Queue and sends them to the relevant chats (or all).
    """

    def __init__(self, token: str, bot_queue):
        log_event("TelegramBotHandler __init__ called")
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

        # Inline button handlers
        self.app.add_handler(CallbackQueryHandler(self.handle_csv_selection, pattern="^csv_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_climate_csv_selection, pattern="^climate_csv_"))
        self.app.add_handler(CallbackQueryHandler(self.handle_sales_selection))

        # Single text handler to process manual entry or fallback
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # ------------------------ Connectivity self-heal (fast path first) ------------------------

    async def _run_cmd(self, cmd):
        """Run a shell command in a worker thread; return the exit code and log on failure."""
        def _do():
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode != 0:
                log_event(f"CMD fail: {' '.join(cmd)} -> {p.returncode} | {p.stderr.strip()}")
            return p.returncode
        return await asyncio.to_thread(_do)

    async def _dns_ok(self) -> bool:
        """Resolve api.telegram.org quickly (no external process)."""
        try:
            loop = asyncio.get_running_loop()
            await loop.getaddrinfo("api.telegram.org", 443, proto=socket.IPPROTO_TCP)
            return True
        except Exception:
            return False

    async def _ensure_network(self) -> bool:
        """
        Try to make networking usable:
        - Fast check: DNS resolution; if ok, we’re done.
        - If DNS fails, check basic internet (ICMP). If broken, try to bring links/profiles up.
        - If internet works but DNS is still broken, set fallback DNS at runtime and flush cache.
        Kept intentionally short; only called after an actual send failure to avoid slowdown.
        """
        # Fast path: if DNS resolves, assume everything is fine
        if await self._dns_ok():
            return True

        # Check raw reachability
        ping_ok = (await self._run_cmd(["ping", "-c", "1", "-W", "2", "1.1.1.1"])) == 0

        # Try to (re)connect links and profiles
        if ETH_CONN_NAME:
            await self._run_cmd(["nmcli", "device", "connect", "eth0"])
            await self._run_cmd(["nmcli", "con", "up", ETH_CONN_NAME])

        await self._run_cmd(["nmcli", "radio", "wifi", "on"])
        await self._run_cmd(["nmcli", "device", "connect", "wlan0"])
        await self._run_cmd(["nmcli", "con", "up", WIFI_CONN_NAME])

        # If link works but DNS is bad, set runtime DNS and flush cache
        if ping_ok and not await self._dns_ok():
            await self._run_cmd(["resolvectl", "dns", "wlan0", "1.1.1.1", "8.8.8.8"])
            await self._run_cmd(["resolvectl", "flush-caches"])

        # Brief settle
        await asyncio.sleep(2)

        # Final check
        return await self._dns_ok()

    # -----------------------------------------------------------------------------------------

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Register a new chat ID and confirm the bot is online."""
        log_event("start_command called")
        chat_id = update.effective_chat.id
        await self._retry(update.message.reply_text, "✅ Bot is online! I'll notify you of purchases.")

        # Load existing chat IDs; add if missing
        chat_ids = load_chat_ids()
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            save_chat_ids(chat_ids)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Example command that calls a function to generate info."""
        log_event("info_command called")
        info_text = generate_locker_info()  # from utils.py
        await self._retry(update.message.reply_text, info_text)

    async def sales_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Presents an inline keyboard with multiple time-period options:
        - This Year, This Month, Last Year, Last Month, Today, Yesterday, Total, Manual Entry
        """
        log_event("sales_command called")
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
        await self._retry(update.message.reply_text, "Please select a time period for the sales report:", reply_markup=reply_markup)

    async def csv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Same options as /sales but will produce a CSV file instead of text/charts."""
        log_event("csv_command called")
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
        await self._retry(update.message.reply_text, "Please select a time period for the CSV export:", reply_markup=reply_markup)

    async def climate_csv_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Same options as /csv, but for climate data instead of sales."""
        log_event("climate_csv_command called")
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
        await self._retry(update.message.reply_text, "Please select a time period for the climate CSV export:", reply_markup=reply_markup)

    async def climate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Responds with the latest climate reading and average (today, yesterday, last 30 days),
        or "ND" if no data is found for a particular period.
        Uses emojis for temperature (🌡) and humidity (💧).
        """
        log_event("climate_command called")
        from utils import get_climate_stats
        stats = get_climate_stats()

        def fmt_line(label, t, h):
            if t is None or h is None:
                return f"{label}: ND"
            return f"{label}: 🌡{t:.1f}°C | 💧{h:.1f}%"

        lines = []
        lines.append(fmt_line("Current", stats["current_temp"], stats["current_hum"]))
        lines.append(fmt_line("Today", stats["avg_today_temp"], stats["avg_today_hum"]))
        lines.append(fmt_line("Yesterday", stats["avg_yesterday_temp"], stats["avg_yesterday_hum"]))
        lines.append(fmt_line("Last 30 days", stats["avg_30days_temp"], stats["avg_30days_hum"]))

        msg_text = "\n".join(lines)
        await self._retry(update.message.reply_text, msg_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sends a list of available commands with brief descriptions (with emojis)."""
        log_event("help_command called")
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
        log_event("handle_sales_selection called")
        query = update.callback_query
        await query.answer()

        data = query.data
        if data in ["this_year", "this_month", "last_year", "last_month", "today", "yesterday", "total"]:
            label = data.replace("_", " ").title()
            await self.sales(label)
        elif data == "manual_entry":
            context.user_data["sales_step"] = "start_date"
            await self._retry(query.edit_message_text, "Please enter the start date (YYYY-MM-DD):")

    async def handle_csv_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks for CSV export."""
        log_event("handle_csv_selection called")
        query = update.callback_query
        await query.answer()
        data = query.data

        if data in ["csv_this_year", "csv_this_month", "csv_last_year", "csv_last_month", "csv_today", "csv_yesterday", "csv_total"]:
            label = data.replace("csv_", "").replace("_", " ").title()
            await self.send_csv_report(label)
        elif data == "csv_manual_entry":
            context.user_data["csv_step"] = "start_date"
            await self._retry(query.edit_message_text, "Please enter the start date (YYYY-MM-DD) for CSV export:")

    async def handle_climate_csv_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks for climate CSV export."""
        log_event("handle_climate_csv_selection called")
        query = update.callback_query
        await query.answer()
        data = query.data

        if data in ["climate_csv_this_year", "climate_csv_this_month", "climate_csv_last_year", "climate_csv_last_month", "climate_csv_today", "climate_csv_yesterday", "climate_csv_total"]:
            label = data.replace("climate_csv_", "").replace("_", " ").title()
            await self.send_climate_csv_report(label)
        elif data == "climate_csv_manual_entry":
            context.user_data["climate_csv_step"] = "start_date"
            await self._retry(query.edit_message_text, "Please enter the start date (YYYY-MM-DD) for climate CSV export:")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Single text handler that:
        - If user_data indicates a /climate_csv manual entry, handle it.
        - Else if user_data indicates a /csv manual entry, handle it.
        - Else if user_data indicates a /sales manual entry, handle it.
        - Otherwise, fallback and just echo (currently no echo).
        """
        log_event("handle_text called")

        if "climate_csv_step" in context.user_data:
            step = context.user_data["climate_csv_step"]

            if step == "start_date":
                context.user_data["climate_csv_start"] = update.message.text
                context.user_data["climate_csv_step"] = "end_date"
                await self._retry(update.message.reply_text, "Please enter the end date (YYYY-MM-DD) for climate CSV export:")
                return

            elif step == "end_date":
                context.user_data["climate_csv_end"] = update.message.text
                start_date = context.user_data["climate_csv_start"]
                end_date = context.user_data["climate_csv_end"]
                period_label = f"{start_date} to {end_date}"
                await self.send_climate_csv_report(period_label)
                context.user_data.clear()
                return

        if "csv_step" in context.user_data:
            step = context.user_data["csv_step"]

            if step == "start_date":
                context.user_data["csv_start_date"] = update.message.text
                context.user_data["csv_step"] = "end_date"
                await self._retry(update.message.reply_text, "Please enter the end date (YYYY-MM-DD) for CSV export:")
                return

            elif step == "end_date":
                context.user_data["csv_end_date"] = update.message.text
                start_date = context.user_data["csv_start_date"]
                end_date = context.user_data["csv_end_date"]
                period_label = f"{start_date} to {end_date}"
                await self.send_csv_report(period_label)
                context.user_data.clear()
                return

        if "sales_step" in context.user_data:
            step = context.user_data["sales_step"]

            if step == "start_date":
                context.user_data["start_date"] = update.message.text
                context.user_data["sales_step"] = "end_date"
                await self._retry(update.message.reply_text, "Please enter the end date (YYYY-MM-DD):")
                return

            elif step == "end_date":
                context.user_data["end_date"] = update.message.text
                start_date = context.user_data["start_date"]
                end_date = context.user_data["end_date"]
                period_label = f"{start_date} to {end_date}"
                await self.sales(period_label)
                context.user_data.clear()
                return

        # Fallback if no manual entry is in progress.
        await self._retry(
            # update.message.reply_text,
            # f"You said: {update.message.text}"
        )

    async def sales(self, period: str):
        log_event(f"sales called with period: {period}")
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[sales] No chat IDs found. Nobody to send the sales report to.")
            return

        report_text, line_chart_path, pie_chart_path = generate_sales_report(period)
        for cid in all_chat_ids:
            await self._send_message_with_retries(cid, report_text)
            if line_chart_path and os.path.isfile(line_chart_path):
                await self._send_photo_with_retries(cid, line_chart_path, caption="Sales Over Time")
            if pie_chart_path and os.path.isfile(pie_chart_path):
                await self._send_photo_with_retries(cid, pie_chart_path, caption="Best Selling Lockers")

    async def _retry(self, func, *args, retries=5, **kwargs):
        """
        Helper function to retry a Telegram API call.
        Handles Timeout/Network/DNS (with self-heal), RetryAfter (flood control), and BadRequest.
        """
        log_event("_retry called")
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)

            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 2))
                log_event(f"_retry RetryAfter {wait}s on attempt {attempt+1}")
                await asyncio.sleep(wait)

            except (TimedOut, NetworkError) as e:
                log_event(f"_retry network issue on attempt {attempt+1}: {e}")
                await self._ensure_network()
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

            except BadRequest as e:
                log_event(f"_retry BadRequest: {e}")
                print(f"BadRequest: {e}")
                return

            except Exception as e:
                log_event(f"_retry Exception on attempt {attempt+1}: {e}")
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

    async def _send_message_with_retries(self, chat_id, text, retries=5):
        """
        Send a message to a specific chat ID with retry logic.
        Fast path: try send immediately; only heal network on failure.
        """
        log_event(f"_send_message_with_retries called for chat_id={chat_id}")

        for attempt in range(retries):
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=text)
                print(f"[TelegramBotHandler] Message sent to {chat_id}")
                log_event(f"Message sent to {chat_id}")
                return

            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 2))
                log_event(f"RetryAfter {wait}s on attempt {attempt+1}")
                await asyncio.sleep(wait)

            except (TimedOut, NetworkError) as e:
                log_event(f"Network issue on attempt {attempt+1}: {e}")
                await self._ensure_network()
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

            except BadRequest as e:
                log_event(f"_send_message_with_retries BadRequest for chat_id={chat_id}: {e}")
                print(f"[TelegramBotHandler] BadRequest to {chat_id}: {e}")
                return

            except Exception as e:
                log_event(f"_send_message_with_retries Exception on attempt {attempt+1} for chat_id={chat_id}: {e}")
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

        print(f"[TelegramBotHandler] Failed to send message to {chat_id} after {retries} attempts.")
        log_event(f"Failed to send message to {chat_id} after {retries} attempts.")
        return

    async def _send_photo_with_retries(self, chat_id, image_path, caption="", retries=5):
        """
        Send a photo to a specific chat ID with retry logic.
        Fast path: try send immediately; only heal network on failure.
        """
        log_event(f"_send_photo_with_retries called for chat_id={chat_id}, image_path={image_path}")

        if not os.path.isfile(image_path):
            log_event(f"Photo path not found: {image_path}")
            print(f"[TelegramBotHandler] Photo path not found: {image_path}")
            return

        for attempt in range(retries):
            try:
                with open(image_path, "rb") as f:
                    await self.app.bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
                print(f"[TelegramBotHandler] Photo sent to {chat_id}")
                log_event(f"Photo sent to {chat_id}")
                return

            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 2))
                log_event(f"RetryAfter {wait}s on attempt {attempt+1} (photo)")
                await asyncio.sleep(wait)

            except (TimedOut, NetworkError) as e:
                log_event(f"Network issue on attempt {attempt+1} (photo): {e}")
                await self._ensure_network()
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

            except BadRequest as e:
                log_event(f"_send_photo_with_retries BadRequest for chat_id={chat_id}: {e}")
                print(f"[TelegramBotHandler] BadRequest (photo) to {chat_id}: {e}")
                return

            except Exception as e:
                log_event(f"_send_photo_with_retries Exception on attempt {attempt+1} for chat_id={chat_id}: {e}")
                backoff = 0.5 if attempt == 0 else min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

        print(f"[TelegramBotHandler] Failed to send photo to {chat_id} after {retries} attempts.")
        log_event(f"Failed to send photo to {chat_id} after {retries} attempts.")
        return

    async def send_csv_report(self, period: str):
        """Generate a CSV for the specified period and broadcast it to all known chat IDs."""
        log_event(f"send_csv_report called for period={period}")
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[send_csv_report] No chat IDs found. Nobody to send CSV to.")
            log_event("No chat IDs found in send_csv_report")
            return

        from utils import generate_csv_file
        csv_path = generate_csv_file(period)
        print(f"[send_csv_report] generate_csv_file returned: {csv_path}")
        log_event(f"generate_csv_file returned: {csv_path}")

        if not csv_path:
            msg_text = f"No CSV data found for period: {period}"
            for cid in all_chat_ids:
                await self._send_message_with_retries(cid, msg_text)
            return

        for cid in all_chat_ids:
            await self._send_document_with_retries(cid, csv_path, caption=f"CSV Data for {period}")

    async def send_climate_csv_report(self, period: str):
        """Generate a climate CSV for the specified period and broadcast to all known chat IDs."""
        log_event(f"send_climate_csv_report called for period={period}")
        all_chat_ids = load_chat_ids()
        if not all_chat_ids:
            print("[send_climate_csv_report] No chat IDs found. Nobody to send climate CSV to.")
            log_event("No chat IDs found in send_climate_csv_report")
            return

        from utils import generate_climate_csv_file
        csv_path = generate_climate_csv_file(period)
        print(f"[send_climate_csv_report] generate_climate_csv_file returned: {csv_path}")
        log_event(f"generate_climate_csv_file returned: {csv_path}")

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
        Fast path: try send immediately; only heal network on failure.
        """
        log_event(f"_send_document_with_retries called for chat_id={chat_id}, file_path={file_path}")

        if not os.path.isfile(file_path):
            log_event(f"Document path not found: {file_path}")
            print(f"[TelegramBotHandler] Document path not found: {file_path}")
            return

        for attempt in range(retries):
            try:
                with open(file_path, "rb") as doc:
                    await self.app.bot.send_document(chat_id=chat_id, document=doc, caption=caption)
                print(f"[TelegramBotHandler] Document sent to {chat_id}")
                log_event(f"Document sent to {chat_id}")
                return

            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 2))
                log_event(f"RetryAfter {wait}s on attempt {attempt+1} (document)")
                await asyncio.sleep(wait)

            except (TimedOut, NetworkError) as e:
                log_event(f"Network issue on attempt {attempt+1} (document): {e}")
                await self._ensure_network()
                backoff = min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

            except BadRequest as e:
                log_event(f"_send_document_with_retries BadRequest for chat_id={chat_id}: {e}")
                print(f"[TelegramBotHandler] BadRequest (document) to {chat_id}: {e}")
                return

            except Exception as e:
                log_event(f"_send_document_with_retries Exception on attempt {attempt+1} for chat_id={chat_id}: {e}")
                backoff = min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

        print(f"[TelegramBotHandler] Failed to send document after {retries} attempts.")
        log_event(f"Failed to send document after {retries} attempts.")
        return

    async def run_bot(self):
        """
        1) Initialize and start the bot.
        2) Start polling.
        3) Start a background task to read from the queue.
        4) Keep running until the process is stopped.
        5) Ensure a graceful shutdown on exit.
        """
        log_event("run_bot called")
        try:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            await self.app.bot.set_my_commands([
                BotCommand("start", "Confirm the bot is online"),
                BotCommand("info", "Display locker info/status"),
                BotCommand("sales", "Generate sales reports"),
                BotCommand("csv", "Generate sales CSV files"),
                BotCommand("climate", "Show climate readings"),
                BotCommand("climate_csv", "Generate climate CSV files"),
                BotCommand("help", "Show help commands"),
            ])

            queue_task = asyncio.create_task(self.read_queue_loop())
            await queue_task

        except Exception as e:
            log_event(f"run_bot exception: {e}")
            print(f"[TelegramBotHandler] Caught exception: {e}")

        finally:
            log_event("run_bot finally block - stopping updater")
            print("[TelegramBotHandler] Stopping updater...")
            try:
                await self.app.updater.stop()
                await self.app.stop()
                print("[TelegramBotHandler] Bot shutdown complete.")
                log_event("Bot shutdown complete")
            except TimedOut:
                log_event("TimedOut during shutdown, suppressing error")
                print("[TelegramBotHandler] Timed out during shutdown, suppressing error.")

    async def stop_bot(self):
        """Custom stop method to suppress the 'get_updates' error during shutdown."""
        log_event("stop_bot called")
        try:
            print("[TelegramBotHandler] Stopping bot gracefully...")
            await self.app.stop()
        except TimedOut:
            log_event("TimedOut error suppressed during stop_bot")
            print("[TelegramBotHandler] Suppressing TimedOut error during shutdown.")

    async def read_queue_loop(self):
        """
        Continuously read messages from the multiprocessing.Queue.
        If 'chat_id' is None, broadcast to ALL saved IDs.
        If 'chat_id' is an integer, send only to that one chat.
        Now also checks for 'image_path' to send an image instead of text.
        """
        log_event("read_queue_loop started")
        while True:
            msg = await asyncio.to_thread(self.bot_queue.get)
            log_event(f"read_queue_loop got message: {msg}")

            if msg is None:
                log_event("read_queue_loop received stop signal")
                print("[TelegramBotHandler] Received stop signal from queue.")
                break

            chat_id = msg.get("chat_id")
            if "image_path" in msg:
                image_path = msg["image_path"]
                caption = msg.get("caption", "")
                await self._send_photo_with_retries(chat_id, image_path, caption)
            else:
                text = msg.get("text", "No text found")
                if chat_id is None:
                    all_chat_ids = load_chat_ids()
                    if not all_chat_ids:
                        print("[TelegramBotHandler] No chat IDs found. Skipping broadcast.")
                        log_event("No chat IDs to broadcast to")
                        continue
                    for cid in all_chat_ids:
                        await self._send_message_with_retries(cid, text)
                else:
                    await self._send_message_with_retries(chat_id, text)
