# utils.py
import json
import os
import csv
from datetime import datetime, timedelta
from collections import Counter

from google_auth import load_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

from admin_windows import InformationWindow


LOG_FOLDER = "logs"

try:
    import serial
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    serial_enabled = True
except (ImportError, serial.SerialException):
    ser = None
    serial_enabled = False

def load_locker_data():
    try:
        with open('lockers.json', 'r') as f:
            data = json.load(f)

        # Add default status if missing in any locker
        for locker_id in data:
            if "status" not in data[locker_id]:
                data[locker_id]["status"] = True  # Default to available

        return data

    except FileNotFoundError:
        # Create default data if file does not exist
        return {str(i): {"locker_id": i, "price": 5.0, "status": True} for i in range(1, 13)}



def save_locker_data(data):
    with open('lockers.json', 'w') as f:
        json.dump(data, f, indent=4)


def send_command(command):
    if serial_enabled and ser:
        ser.write(command.encode())
        ser.flush()
    else:
        print(f"Mock UART Command Sent: {command}")


#Ensure the log folder exists
def initialize_logger():
    """Ensure the log folder exists."""
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)

#Function to log an event
def log_event(locker_id, price):
    """
    Log an event to multiple structured log files.
    :param locker_id: Locker ID
    :param price: Price associated with the locker
    """
    initialize_logger()

    # Determine current date and time
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    current_year = now.strftime("%Y")
    current_month = now.strftime("%m")
    current_day = now.strftime("%d")

    # Define log file paths
    master_log = os.path.join(LOG_FOLDER, "logs.csv")  # All-time logs
    yearly_log = os.path.join(LOG_FOLDER, f"logs_{current_year}.csv")  # Yearly logs
    monthly_log = os.path.join(LOG_FOLDER, f"logs_{current_year}_{current_month}.csv")  # Monthly logs
    daily_log = os.path.join(LOG_FOLDER, f"logs_{current_year}_{current_month}_{current_day}.csv")  # Daily logs

    # Prepare the log entry
    log_entry = [current_date, current_time, locker_id, price]

    # Write to all log files
    write_to_log(master_log, log_entry, ["Date", "Time", "Locker ID", "Price"])
    write_to_log(yearly_log, log_entry, ["Date", "Time", "Locker ID", "Price"])
    write_to_log(monthly_log, log_entry, ["Date", "Time", "Locker ID", "Price"])
    write_to_log(daily_log, log_entry, ["Date", "Time", "Locker ID", "Price"])

    # Manage expired logs
    manage_expired_logs(now)


def write_to_log(file_path, log_entry, header):
    """
    Write a log entry to the specified file. Add a header if the file doesn't exist.
    :param file_path: Path to the log file
    :param log_entry: List containing the log details
    :param header: List containing the header row
    """
    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(header)  # Write header if the file is new
        writer.writerow(log_entry)  # Write the log entry


def manage_expired_logs(now):
    """
    Delete expired logs for last day, last month, and last year if they are at least one minute expired.
    :param now: The current datetime object.
    """
    # Define the expiration threshold (5 minute before now)
    expiration_time = now - timedelta(minutes=5)

    # Last day's log file
    yesterday = now - timedelta(days=1)
    yesterday_log = os.path.join(
        LOG_FOLDER, f"logs_{yesterday.strftime('%Y')}_{yesterday.strftime('%m')}_{yesterday.strftime('%d')}.csv"
    )
    if os.path.exists(yesterday_log) and is_file_expired(yesterday_log, expiration_time):
        os.remove(yesterday_log)
        print(f"Deleted yesterday's log file: {yesterday_log}")

    # Last month's log file
    last_month = (now.replace(day=1) - timedelta(days=1))  # Go to the last day of the previous month
    last_month_log = os.path.join(
        LOG_FOLDER, f"logs_{last_month.strftime('%Y')}_{last_month.strftime('%m')}.csv"
    )
    if os.path.exists(last_month_log) and is_file_expired(last_month_log, expiration_time):
        os.remove(last_month_log)
        print(f"Deleted last month's log file: {last_month_log}")

    # Last year's log file
    last_year = now.replace(year=now.year - 1, month=12, day=31)  # Last day of the previous year
    last_year_log = os.path.join(LOG_FOLDER, f"logs_{last_year.strftime('%Y')}.csv")
    if os.path.exists(last_year_log) and is_file_expired(last_year_log, expiration_time):
        os.remove(last_year_log)
        print(f"Deleted last year's log file: {last_year_log}")


def is_file_expired(file_path, expiration_time):
    """
    Check if a file's last modification time is older than the expiration time.
    :param file_path: Path to the file.
    :param expiration_time: Datetime object representing the expiration threshold.
    :return: True if the file is expired, False otherwise.
    """
    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    return file_mod_time < expiration_time



def upload_file_to_drive(file_path, folder_id=None):
    """Uploads a file to Google Drive."""
    creds = load_credentials('credentials/drive_token.json')
    if not creds:
        raise Exception("Google Drive credentials not found. Please authenticate.")

    # Initialize Drive API client
    service = build('drive', 'v3', credentials=creds)

    #delete_all_files_from_drive(creds, service)
    delete_file_from_drive_by_name(creds, service, os.path.basename(file_path))

    # Delete a file that is two days old
    two_days_ago = datetime.now() - timedelta(days=2)
    old_file_name = f"logs_{two_days_ago.strftime('%Y_%m_%d')}.csv"  
    delete_file_from_drive_by_name(creds, service, old_file_name)

    # Prepare file metadata
    file_metadata = {'name': file_path.split('/')[-1]}  # Extract file name from file_path
    if folder_id:
        file_metadata['parents'] = [folder_id]

    # Use MediaFileUpload for media_body
    media = MediaFileUpload(file_path, resumable=True)

    # Upload the file
    uploaded_file = service.files().create(body=file_metadata, media_body=media).execute()
    print(f"File uploaded: {uploaded_file['name']} (ID: {uploaded_file['id']})")



def delete_all_files_from_drive(creds, service):
    """
    Deletes all files from the authenticated Google Drive account.
    """
    # Load credentials from the token file
    #creds = load_credentials('credentials/token.json')
    #if not creds:
    #    raise Exception("Google Drive credentials not found. Please authenticate.")

    # Initialize Google Drive API client
    #service = build('drive', 'v3', credentials=creds)

    try:
        # List all files in the user's Drive
        results = service.files().list(fields="files(id, name)").execute()
        files = results.get('files', [])

        if not files:
            print("No files found in your Google Drive.")
            return

        # Iterate through each file and delete it
        for file in files:
            file_id = file['id']
            file_name = file['name']
            try:
                service.files().delete(fileId=file_id).execute()
                print(f"Deleted: {file_name} (ID: {file_id})")
            except Exception as e:
                print(f"Failed to delete file: {file_name} (ID: {file_id}), Error: {e}")

        print("All files have been deleted from Google Drive.")

    except Exception as e:
        print(f"An error occurred: {e}")


def delete_file_from_drive_by_name(creds, service, file_name):
    """
    Deletes a file from Google Drive by its name.
    :param file_name: The name of the file to delete.
    """
    # Load credentials from the token file
    #creds = load_credentials('credentials/token.json')
    #if not creds:
    #    raise Exception("Google Drive credentials not found. Please authenticate.")

    # Initialize Google Drive API client
    #service = build('drive', 'v3', credentials=creds)

    try:
        # Search for the file by name
        results = service.files().list(
            q=f"name='{file_name}'",  # Query to find files matching the name
            fields="files(id, name)"
        ).execute()

        files = results.get('files', [])

        if not files:
            print(f"No file named '{file_name}' was found on Google Drive.")
            return

        # Iterate through all matching files (there might be duplicates)
        for file in files:
            file_id = file['id']
            file_name = file['name']
            try:
                service.files().delete(fileId=file_id).execute()
                print(f"Deleted: {file_name} (ID: {file_id})")
            except Exception as e:
                print(f"Failed to delete file: {file_name} (ID: {file_id}), Error: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")


 
def send_email(subject, body, recipient_email, attachment_file=None):
    """
    Send an email using Gmail API with an optional attachment.
    :param subject: Subject of the email.
    :param body: Body of the email.
    :param recipient_email: Recipient's email address.
    :param attachment_file: Path to the file to attach (optional).
    """
    creds = load_credentials('credentials/gmail_token.json')
    if not creds:
        raise Exception("Gmail credentials not found. Please authenticate.")

    # Initialize Gmail API client
    service = build('gmail', 'v1', credentials=creds)

    # Create the email message with MIMEMultipart
    message = MIMEMultipart()
    message['to'] = recipient_email
    message['subject'] = subject

    # Add email body
    message.attach(MIMEText(body, 'plain'))

    # Attach file if provided
    if attachment_file:
        try:
            with open(attachment_file, 'rb') as f:
                mime_base = MIMEBase('application', 'octet-stream')
                mime_base.set_payload(f.read())
                encoders.encode_base64(mime_base)
                mime_base.add_header(
                    'Content-Disposition',
                    f'attachment; filename={attachment_file.split("/")[-1]}'
                )
                message.attach(mime_base)
        except FileNotFoundError:
            print(f"Error: Attachment file '{attachment_file}' not found.")
            return

    # Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send the email
    send_request = {'raw': raw_message}
    sent_message = service.users().messages().send(userId="me", body=send_request).execute()
    print(f"Email sent: {sent_message['id']}")  



def send_email_all(subject, body, attachment_file=None):
    """
    Send an email to multiple recipients by reading addresses from a .txt file.
    :param subject: Subject of the email.
    :param body: Body of the email.
    :param attachment_file: Path to the file to attach (optional).
    :param email_file_path: Path to the .txt file containing email addresses.
    """
    email_file_path="email_adresses.txt"
    creds = load_credentials('credentials/gmail_token.json')
    if not creds:
        raise Exception("Gmail credentials not found. Please authenticate.")

    # Initialize Gmail API client
    service = build('gmail', 'v1', credentials=creds)

    # Read email addresses from the file
    try:
        with open(email_file_path, 'r') as email_file:
            email_addresses = [line.strip().strip(';') for line in email_file.readlines()]
    except FileNotFoundError:
        print(f"Error: Email addresses file '{email_file_path}' not found.")
        return

    for recipient_email in email_addresses:
        if not recipient_email:  # Skip empty lines
            continue
        try:
            # Create the email message with MIMEMultipart
            message = MIMEMultipart()
            message['to'] = recipient_email
            message['subject'] = subject

            # Add email body
            message.attach(MIMEText(body, 'plain'))

            # Attach file if provided
            if attachment_file:
                try:
                    with open(attachment_file, 'rb') as f:
                        mime_base = MIMEBase('application', 'octet-stream')
                        mime_base.set_payload(f.read())
                        encoders.encode_base64(mime_base)
                        mime_base.add_header(
                            'Content-Disposition',
                            f'attachment; filename={attachment_file.split("/")[-1]}'
                        )
                        message.attach(mime_base)
                except FileNotFoundError:
                    print(f"Error: Attachment file '{attachment_file}' not found.")
                    continue

            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            # Send the email
            send_request = {'raw': raw_message}
            sent_message = service.users().messages().send(userId="me", body=send_request).execute()
            print(f"Email sent to {recipient_email}: {sent_message['id']}")

        except Exception as e:
            print(f"Failed to send email to {recipient_email}: {e}")




def generate_summary_from_logs(file_path):
    """
    Generates a well-structured summary from the vending machine log file.
    :param file_path: Path to the log file (CSV).
    :return: A formatted summary text.
    """
    try:
        # Check if the file exists
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Initialize counters
            total_earnings = 0
            total_purchases = 0
            daily_sales = Counter()
            locker_sales = Counter()

            # Process each row in the CSV
            for row in reader:
                try:
                    date = row["Date"]
                    locker_id = row["Locker ID"]
                    price = float(row["Price"])
                    
                    total_earnings += price
                    total_purchases += 1
                    daily_sales[date] += 1
                    locker_sales[locker_id] += 1
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid row: {row}, Error: {e}")

        # Calculate top selling days
        top_days = daily_sales.most_common(3)

        # Calculate top selling lockers
        top_lockers = locker_sales.most_common(3)

        # Format the top selling days
        best_selling_days = "\n".join(
            [f"   - {day}: {count} sales" for day, count in top_days]
        )

        # Format the top selling lockers
        best_selling_lockers = "\n".join(
            [f"   - Locker {locker_id}: {count} sales" for locker_id, count in top_lockers]
        )

        # Generate the summary text
        summary = (
            f"This month's summary:\n"
            f"---------------------\n"
            f"Total earnings: €{total_earnings:.2f}\n"
            f"Total purchases: {total_purchases}\n"
            f"\nBest selling days:\n{best_selling_days}\n"
            f"\nBest selling lockers:\n{best_selling_lockers}\n"
        )
        return summary

    except FileNotFoundError:
        return f"Error: The file '{file_path}' does not exist."
    except Exception as e:
        return f"An error occurred: {e}"
    


def generate_summary_from_logs_year(file_path):
    """
    Generates a well-structured summary from the vending machine log file.
    :param file_path: Path to the log file (CSV).
    :return: A formatted summary text.
    """
    try:
        # Check if the file exists
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Initialize counters
            total_earnings = 0
            total_purchases = 0
            daily_sales = Counter()
            locker_sales = Counter()

            # Process each row in the CSV
            for row in reader:
                try:
                    date = row["Date"]
                    locker_id = row["Locker ID"]
                    price = float(row["Price"])
                    
                    total_earnings += price
                    total_purchases += 1
                    daily_sales[date] += 1
                    locker_sales[locker_id] += 1
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid row: {row}, Error: {e}")

        # Calculate top selling days
        top_days = daily_sales.most_common(3)

        # Calculate top selling lockers
        top_lockers = locker_sales.most_common(3)

        # Format the top selling days
        best_selling_days = "\n".join(
            [f"   - {day}: {count} sales" for day, count in top_days]
        )

        # Format the top selling lockers
        best_selling_lockers = "\n".join(
            [f"   - Locker {locker_id}: {count} sales" for locker_id, count in top_lockers]
        )

        # Generate the summary text
        summary = (
            f"Happy New Year\n"
            f"This years's summary:\n"
            f"---------------------\n"
            f"Total earnings: €{total_earnings:.2f}\n"
            f"Total purchases: {total_purchases}\n"
            f"\nBest selling days:\n{best_selling_days}\n"
            f"\nBest selling lockers:\n{best_selling_lockers}\n"
        )
        return summary

    except FileNotFoundError:
        return f"Error: The file '{file_path}' does not exist."
    except Exception as e:
        return f"An error occurred: {e}"
    

def generate_summary_from_logs_lv(file_path):
    """
    Generates a well-structured summary from the vending machine log file in Latvian.
    :param file_path: Path to the log file (CSV).
    :return: A formatted summary text in Latvian.
    """
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Initialize counters
            total_earnings = 0
            total_purchases = 0
            daily_sales = Counter()
            locker_sales = Counter()

            # Process each row in the CSV
            for row in reader:
                try:
                    date = row["Date"]
                    locker_id = row["Locker ID"]
                    price = float(row["Price"])
                    
                    total_earnings += price
                    total_purchases += 1
                    daily_sales[date] += 1
                    locker_sales[locker_id] += 1
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid row: {row}, Error: {e}")

        # Calculate top selling days
        top_days = daily_sales.most_common(3)

        # Calculate top selling lockers
        top_lockers = locker_sales.most_common(3)

        # Format the top selling days
        best_selling_days = "\n".join(
            [f"   - {day}: {count} pirkumi" for day, count in top_days]
        )

        # Format the top selling lockers
        best_selling_lockers = "\n".join(
            [f"   - Skapītis {locker_id}: {count} pirkumi" for locker_id, count in top_lockers]
        )

        # Generate the summary text
        summary = (
            f"Šī mēneša kopsavilkums:\n"
            f"-----------------------\n"
            f"Kopējie ieņēmumi: €{total_earnings:.2f}\n"
            f"Kopējais pirkumu skaits: {total_purchases}\n"
            f"\nLabākās pārdošanas dienas:\n{best_selling_days}\n"
            f"\nLabāk pārdotie skapīši:\n{best_selling_lockers}\n"
        )
        return summary

    except FileNotFoundError:
        return f"Kļūda: Fails '{file_path}' neeksistē."
    except Exception as e:
        return f"Radās kļūda: {e}"
    

def generate_summary_from_logs_de(file_path):
    """
    Generates a well-structured summary from the vending machine log file in German.
    :param file_path: Path to the log file (CSV).
    :return: A formatted summary text in German.
    """
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Initialize counters
            total_earnings = 0
            total_purchases = 0
            daily_sales = Counter()
            locker_sales = Counter()

            # Process each row in the CSV
            for row in reader:
                try:
                    date = row["Date"]
                    locker_id = row["Locker ID"]
                    price = float(row["Price"])
                    
                    total_earnings += price
                    total_purchases += 1
                    daily_sales[date] += 1
                    locker_sales[locker_id] += 1
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid row: {row}, Error: {e}")

        # Calculate top selling days
        top_days = daily_sales.most_common(3)

        # Calculate top selling lockers
        top_lockers = locker_sales.most_common(3)

        # Format the top selling days
        best_selling_days = "\n".join(
            [f"   - {day}: {count} Verkäufe" for day, count in top_days]
        )

        # Format the top selling lockers
        best_selling_lockers = "\n".join(
            [f"   - Schließfach {locker_id}: {count} Verkäufe" for locker_id, count in top_lockers]
        )

        # Generate the summary text
        summary = (
            f"Zusammenfassung des Monats:\n"
            f"----------------------------\n"
            f"Gesamteinnahmen: €{total_earnings:.2f}\n"
            f"Gesamtkäufe: {total_purchases}\n"
            f"\nBeste Verkaufstage:\n{best_selling_days}\n"
            f"\nMeistverkaufte Schließfächer:\n{best_selling_lockers}\n"
        )
        return summary

    except FileNotFoundError:
        return f"Fehler: Die Datei '{file_path}' existiert nicht."
    except Exception as e:
        return f"Ein Fehler ist aufgetreten: {e}"


def generate_summary_from_logs_ru(file_path):
    """
    Generates a well-structured summary from the vending machine log file in Russian.
    :param file_path: Path to the log file (CSV).
    :return: A formatted summary text in Russian.
    """
    try:
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)

            # Initialize counters
            total_earnings = 0
            total_purchases = 0
            daily_sales = Counter()
            locker_sales = Counter()

            # Process each row in the CSV
            for row in reader:
                try:
                    date = row["Date"]
                    locker_id = row["Locker ID"]
                    price = float(row["Price"])
                    
                    total_earnings += price
                    total_purchases += 1
                    daily_sales[date] += 1
                    locker_sales[locker_id] += 1
                except (KeyError, ValueError) as e:
                    print(f"Skipping invalid row: {row}, Error: {e}")

        # Calculate top selling days
        top_days = daily_sales.most_common(3)

        # Calculate top selling lockers
        top_lockers = locker_sales.most_common(3)

        # Format the top selling days
        best_selling_days = "\n".join(
            [f"   - {day}: {count} продаж" for day, count in top_days]
        )

        # Format the top selling lockers
        best_selling_lockers = "\n".join(
            [f"   - Ячейка {locker_id}: {count} продаж" for locker_id, count in top_lockers]
        )

        # Generate the summary text
        summary = (
            f"Сводка за месяц:\n"
            f"-----------------\n"
            f"Общий доход: €{total_earnings:.2f}\n"
            f"Общее количество покупок: {total_purchases}\n"
            f"\nЛучшие дни продаж:\n{best_selling_days}\n"
            f"\nЛучшие ячейки продаж:\n{best_selling_lockers}\n"
        )
        return summary

    except FileNotFoundError:
        return f"Ошибка: Файл '{file_path}' не существует."
    except Exception as e:
        return f"Произошла ошибка: {e}"


def interpret_and_notify(data):

    if not isinstance(data, (bytes, bytearray)) or len(data) != 5:
        print("Invalid input: Expected a 5-byte sequence.")

    command = data[0]
    byte2 = data[1]
    byte3 = data[2]

    subject = None
    body = None

    if command == 0xF1:  # Problems with lockers
        locker_id = byte2
        subject = "Problems with Locker"
        if byte3 == 50:
            body = f"Locker {locker_id}: Has been opened for an hour."
        elif byte3 == 100:
            body = f"Locker {locker_id}: Was opened for an hour, now closed."
        elif byte3 == 150:
            body = f"Locker {locker_id}: Jammed. Customer has been informed to call support."
            InformationWindow.show()
        else:
            body = f"Locker {locker_id}: Unknown issue (code {byte3})."
        send_email_all(subject, body)

    elif command == 0xF2:  # Problems with I2C devices
        locker_id = byte2
        subject = "Problems with I2C Devices"
        if byte3 == 50:
            body = f"Locker {locker_id}: Issue with price tag display."
        elif byte3 == 100:
            body = f"Locker {locker_id}: Issue with LED stripe driver."
        else:
            body = f"Locker {locker_id}: Unknown issue (code {byte3})."
        send_email_all(subject, body)

    elif command == 0xF3:  # Problems in ventilation system
        ventilation_object = byte2
        subject = "Problems in Ventilation System"
        if byte3 == 50:
            body = f"Ventilation object {ventilation_object}: Fan problem detected."
        elif byte3 == 100:
            body = f"Ventilation object {ventilation_object}: Humidity/temperature sensor issue detected."
        else:
            body = f"Ventilation object {ventilation_object}: Unknown issue (code {byte3})."
        send_email_all(subject, body)

    else:
        print("Unknown command (0x{command:02X}).")


        

