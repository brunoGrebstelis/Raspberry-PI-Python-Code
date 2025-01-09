# utils.py
import json
import os
import csv
import sqlite3
from datetime import datetime, timedelta
from collections import Counter

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

from admin_windows import InformationWindow


LOG_FOLDER = "logs"
DB_FILE = "logs/vending_machine_logs.db"

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


def initialize_database():
    """
    Initialize the database and create the logs table if it doesn't exist.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create a table for logs if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        locker_id INTEGER NOT NULL,
        price REAL NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()


def log_event(locker_id, price):
    """
    Log a purchase event to the SQLite database.
    :param locker_id: Locker ID where the purchase was made.
    :param price: Price of the purchase.
    """
    initialize_database()  # Ensure the database is initialized

    # Get the current date and time
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    # Connect to the database and insert the log entry
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO logs (date, time, locker_id, price)
    VALUES (?, ?, ?, ?)
    ''', (current_date, current_time, locker_id, price))

    conn.commit()
    conn.close()

    print(f"Logged: Locker {locker_id}, Price €{price}, Date {current_date}, Time {current_time}")





def generate_summary(period: str) -> str:
    """
    Generate a well-structured summary from the SQLite database.
    :param period: A string in the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'.
    :return: A formatted summary text.
    """
    # Connect to the database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Determine the query based on the length of the input period
    if len(period) == 4:  # Year
        query = "SELECT date, locker_id, price FROM logs WHERE strftime('%Y', date) = ?"
    elif len(period) == 7:  # Month
        query = "SELECT date, locker_id, price FROM logs WHERE strftime('%Y-%m', date) = ?"
    elif len(period) == 10:  # Day
        query = "SELECT date, locker_id, price FROM logs WHERE date = ?"
    else:
        return "Invalid period format. Use 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'."

    # Execute the query
    cursor.execute(query, (period,))
    logs = cursor.fetchall()
    conn.close()

    # Check if there are no logs for the given period
    if not logs:
        return f"No logs found for the specified period: {period}."

    # Initialize counters
    total_earnings = 0
    total_purchases = 0
    daily_sales = Counter()
    locker_sales = Counter()

    # Process each log entry
    for log in logs:
        date, locker_id, price = log
        total_earnings += price
        total_purchases += 1
        daily_sales[date] += 1
        locker_sales[locker_id] += 1

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
        f"Summary for {period}:\n"
        f"---------------------\n"
        f"Total earnings: €{total_earnings:.2f}\n"
        f"Total purchases: {total_purchases}\n"
        f"\nBest selling days:\n{best_selling_days}\n"
        f"\nBest selling lockers:\n{best_selling_lockers}\n"
    )

    return summary


def generate_locker_info():
    """
    Loads lockers.json and returns a string listing each locker.
    If status is true => show price
    If status is false => show "empty"
    """
    data = load_locker_data()   # This function is already in utils.py
    lines = []
    for locker_id_str, locker_dict in data.items():
        price = locker_dict.get("price", 0)
        status = locker_dict.get("status", True)
        if status:
            lines.append(f"Locker {locker_id_str} = {price}€")
        else:
            lines.append(f"Locker {locker_id_str} = empty")
    return "\n".join(lines)



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
        #send_email_all(subject, body)

    elif command == 0xF2:  # Problems with I2C devices
        locker_id = byte2
        subject = "Problems with I2C Devices"
        if byte3 == 50:
            body = f"Locker {locker_id}: Issue with price tag display."
        elif byte3 == 100:
            body = f"Locker {locker_id}: Issue with LED stripe driver."
        else:
            body = f"Locker {locker_id}: Unknown issue (code {byte3})."
        #send_email_all(subject, body)

    elif command == 0xF3:  # Problems in ventilation system
        ventilation_object = byte2
        subject = "Problems in Ventilation System"
        if byte3 == 50:
            body = f"Ventilation object {ventilation_object}: Fan problem detected."
        elif byte3 == 100:
            body = f"Ventilation object {ventilation_object}: Humidity/temperature sensor issue detected."
        else:
            body = f"Ventilation object {ventilation_object}: Unknown issue (code {byte3})."
        #send_email_all(subject, body)

    else:
        print("Unknown command (0x{command:02X}).")


        

