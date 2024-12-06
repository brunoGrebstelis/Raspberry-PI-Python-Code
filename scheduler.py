import schedule
import time
from threading import Thread
from utils import upload_file_to_drive
from utils import send_email
from utils import generate_summary_from_logs
from utils import generate_summary_from_logs_lv
from utils import generate_summary_from_logs_de
from utils import generate_summary_from_logs_ru

class Scheduler:
    def __init__(self):
        """
        Initialize the scheduler and register tasks.
        """
        self.running = False  # Scheduler status

    def schedule_tasks(self):
        """
        Register tasks to be executed on a schedule.
        """
        # Schedule hourly updates of Drive logs
        schedule.every().hour.at(":59").do(self.hourly_drive_update)

        # Schedule monthly email reports by checking daily at 10:00
        schedule.every().day.at("10:00").do(self.check_and_send_monthly_email_report)

        # Additional tasks can be added here...

    def hourly_drive_update(self):
        """
        Task to perform daily updates on Google Drive.
        - Upload the previous day's log file.
        - Manage log deletion if necessary.
        """
        from datetime import datetime, timedelta
        today = datetime.now()
        log_file = f"logs/logs_{today.strftime('%Y_%m_%d')}.csv"
        log_file2 = f"logs/logs_{today.strftime('%Y')}.csv"

        try:
            # Upload the previous day's log file
            upload_file_to_drive(log_file)
            print(f"Successfully uploaded {log_file} to Google Drive.")
        except FileNotFoundError:
            print(f"No log file found for {today.strftime('%Y-%m-%d')}. Skipping upload.")
        except Exception as e:
            print(f"Failed to upload {log_file}. Error: {e}")

        
        try:
            # Upload the previous day's log file
            upload_file_to_drive(log_file2)
            print(f"Successfully uploaded {log_file2} to Google Drive.")
        except FileNotFoundError:
            print(f"No log file found for {today.strftime('%Y-%m-%d')}. Skipping upload.")
        except Exception as e:
            print(f"Failed to upload {log_file2}. Error: {e}")


        # Optional: Add logic for managing old logs if needed
        self.manage_old_logs()

    def send_monthly_email_report(self):
        """
        Task to send the monthly email report.
        """
        from datetime import datetime
        last_month = datetime.now().strftime('%Y_%m')
        log_file = f"logs/logs_{last_month}.csv"

        subject = f"Monthly Report for {last_month}"
        body = generate_summary_from_logs(log_file)

        try:
            send_email(subject, body, "bgrebstelis@gmail.com", attachment_file=log_file)
            print(f"Monthly email report for {last_month} sent successfully.")
        except FileNotFoundError:
            print(f"No monthly log file found for {last_month}. Email report skipped.")
        except Exception as e:
            print(f"Failed to send monthly email report. Error: {e}")


    def check_and_send_monthly_email_report(self):
        """
        Check if today is the first day of the month and send the monthly email report.
         """
        from datetime import datetime
        today = datetime.now()

        if today.day == 1:  # If it's the first day of the month
            self.send_monthly_email_report()


    def manage_old_logs(self):
        """
        Optional task to clean up or archive old log files.
        - Could delete logs older than a specific duration.
        """
        # Implement logic for managing expired logs here, if needed.
        pass

    def start(self):
        """
        Start the scheduler in a separate thread.
        """
        self.running = True
        self.schedule_tasks()
        Thread(target=self.run, daemon=True).start()  # Run the scheduler in a background thread

    def run(self):
        """
        Continuously run scheduled tasks.
        """
        while self.running:
            schedule.run_pending()
            time.sleep(1)  # Wait 1 second between checks

    def stop(self):
        """
        Stop the scheduler.
        """
        self.running = False
