import schedule
import time
import os
from threading import Thread
from datetime import datetime, timedelta
from utils import generate_sales_report
# from utils import generate_sales_report  # Make sure this is available

class Scheduler:
    def __init__(self, bot_queue):
        self.bot_queue = bot_queue
        self.running = False

    def schedule_tasks(self):
        """
        Daily checks for:
          1) 10:00 => If day == 1 => generate last month's report
          2) 00:00 => If it's Jan 1 => send Happy New Year & last year's report
        """
        schedule.every().day.at("10:00").do(self._monthly_report)
        schedule.every().day.at("00:00").do(self._yearly_report)

    def _monthly_report(self):
        """
        Generates and sends a report for the PREVIOUS month if today is the 1st.
        """
        now = datetime.now()
        # If it’s the 1st day of the month => generate last month’s report
        if now.day == 1:
            # Calculate date range for the previous month
            start_date, end_date = self._get_previous_month_range()
            period_label = f"{start_date} to {end_date}"

            report_text, line_chart_path, pie_chart_path = generate_sales_report(period_label)

            # 1) Enqueue the text report
            text_msg = {
                "chat_id": None,  # broadcast to all
                "text": report_text,
            }
            self.bot_queue.put(text_msg)

            # 2) Enqueue line chart if it exists
            if line_chart_path and os.path.isfile(line_chart_path):
                line_chart_msg = {
                    "chat_id": None,
                    "image_path": line_chart_path,
                    "caption": "Sales Over Time (Previous Month)",
                }
                self.bot_queue.put(line_chart_msg)

            # 3) Enqueue pie chart if it exists
            if pie_chart_path and os.path.isfile(pie_chart_path):
                pie_chart_msg = {
                    "chat_id": None,
                    "image_path": pie_chart_path,
                    "caption": "Best Selling Lockers (Previous Month)",
                }
                self.bot_queue.put(pie_chart_msg)

    def _yearly_report(self):
        """
        Generates and sends a report for the PREVIOUS year if today is Jan 1.
        Also sends a "Happy New Year!" message.
        """
        now = datetime.now()
        # If it’s January 1 => generate last year's report
        if now.day == 1 and now.month == 1:
            # First, enqueue a Happy New Year message
            new_year_msg = {
                "chat_id": None,
                "text": "Happy New Year! 🎉🥂",
            }
            self.bot_queue.put(new_year_msg)

            # Calculate date range for the previous year
            start_date, end_date = self._get_previous_year_range()
            period_label = f"{start_date} to {end_date}"

            report_text, line_chart_path, pie_chart_path = generate_sales_report(period_label)

            # 1) Enqueue the text report
            text_msg = {
                "chat_id": None,
                "text": report_text,
            }
            self.bot_queue.put(text_msg)

            # 2) Enqueue line chart if it exists
            if line_chart_path and os.path.isfile(line_chart_path):
                line_chart_msg = {
                    "chat_id": None,
                    "image_path": line_chart_path,
                    "caption": "Sales Over Time (Previous Year)",
                }
                self.bot_queue.put(line_chart_msg)

            # 3) Enqueue pie chart if it exists
            if pie_chart_path and os.path.isfile(pie_chart_path):
                pie_chart_msg = {
                    "chat_id": None,
                    "image_path": pie_chart_path,
                    "caption": "Best Selling Lockers (Previous Year)",
                }
                self.bot_queue.put(pie_chart_msg)

    def _get_previous_month_range(self):
        """
        Returns (start_date, end_date) for the previous month,
        formatted as 'YYYY-MM-DD'.
        """
        today = datetime.today()
        # The first day of the current month
        first_of_current_month = today.replace(day=1)
        # Last day of the previous month is one day before the first of this month
        last_day_prev_month = first_of_current_month - timedelta(days=1)
        # First day of the previous month
        first_day_prev_month = last_day_prev_month.replace(day=1)

        start_date = first_day_prev_month.strftime("%Y-%m-%d")
        end_date = last_day_prev_month.strftime("%Y-%m-%d")
        return (start_date, end_date)

    def _get_previous_year_range(self):
        """
        Returns (start_date, end_date) for the previous year,
        formatted as 'YYYY-MM-DD'.
        """
        today = datetime.today()
        # "Last year"
        last_year = today.year - 1
        start_of_last_year = datetime(last_year, 1, 1)
        end_of_last_year = datetime(last_year, 12, 31)

        start_date = start_of_last_year.strftime("%Y-%m-%d")
        end_date = end_of_last_year.strftime("%Y-%m-%d")
        return (start_date, end_date)

    def start(self):
        """
        Starts the scheduler in a separate thread.
        """
        self.running = True
        self.schedule_tasks()
        Thread(target=self.run, daemon=True).start()

    def run(self):
        """
        Continuously run scheduled tasks.
        """
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        """
        Stop the scheduler.
        """
        self.running = False
