import schedule
import time
from threading import Thread


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
        #schedule.every().hour.at(":59").do(self.hourly_drive_update)

        # Schedule monthly email reports by checking daily at 10:00
        #schedule.every().day.at("10:00").do(self.check_and_send_monthly_email_report)

        # Schedule yearly email reports by checking yearly at 00:00
        #schedule.every().day.at("00:00").do(self.check_and_send_yearly_report)


        # Test
        #schedule.every().hour.at(":15").do(self.hourly_drive_update)
        #schedule.every().hour.at(":40").do(self.send_monthly_email_report)


    
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
