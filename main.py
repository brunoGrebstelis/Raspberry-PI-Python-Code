# main.py
from app import VendingMachineApp

from utils import upload_file_to_drive
from utils import send_email
from utils import generate_summary_from_logs
from utils import generate_summary_from_logs_lv
from utils import generate_summary_from_logs_de
from utils import generate_summary_from_logs_ru


if __name__ == "__main__":
    #upload_file_to_drive('logs/logs_2024_12.csv')
    send_email(
        subject="Test",
        body=generate_summary_from_logs("logs/logs_2024_12.csv"),
        recipient_email="bgrebstelis@gmail.com",
        attachment_file="logs/logs_2024_12.csv"
    )

    app = VendingMachineApp()
    app.mainloop()

