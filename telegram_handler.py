import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


class TelegramBotHandler:
    """
    A Telegram bot class that manually starts & stops the updater to avoid
    'wait_for_stop()' issues and 'event loop already running' errors.
    """

    def __init__(self, token: str):
        """
        :param token: Your Telegram bot token
        """
        self.app = ApplicationBuilder().token(token).build()

        # Register some handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for the /start command."""
        await update.message.reply_text("✅ Bot is online and ready!")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Echo any text message."""
        message_text = update.message.text
        await update.message.reply_text(f"You said: {message_text}")

    async def run_bot(self):
        """
        Manually handle the bot lifecycle instead of .run_polling() or .wait_for_stop():
          1) initialize the bot
          2) start the bot
          3) start polling
          4) keep running until the process is killed or an error occurs
          5) finally stop & shutdown
        """
        try:
            # 1) Initialize resources
            await self.app.initialize()

            # 2) Start the bot (this sets up internal tasks, etc.)
            await self.app.start()

            # 3) Start polling in a background task
            await self.app.updater.start_polling()

            # 4) Keep the bot running "forever"
            #    In a kiosk or server scenario, you often just let it run until
            #    the process is killed or an exception stops it.
            while True:
                await asyncio.sleep(999999)

        except Exception as e:
            print(f"[TelegramBotHandler] Caught exception: {e}")

        finally:
            print("[TelegramBotHandler] Stopping updater ...")
            await self.app.updater.stop()     # Stop polling
            await self.app.stop()            # Stop the application
            await self.app.shutdown()        # Cleanup resources
            print("[TelegramBotHandler] Bot shutdown complete.")

    def send_message(self, chat_id: int, text: str):
        """
        If you want to send a message programmatically from within the same process,
        you can schedule it on the event loop. This won't work across processes
        without extra inter-process communication.
        """
        asyncio.run_coroutine_threadsafe(
            self.app.bot.send_message(chat_id=chat_id, text=text),
            self.app.runner._loop,
        )
