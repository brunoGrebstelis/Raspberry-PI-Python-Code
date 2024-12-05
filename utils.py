# utils.py
import json
import os
import csv
from datetime import datetime

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
    Log an event to the monthly CSV file.
    :param locker_id: Locker ID
    :param price: Price associated with the locker
    """
    initialize_logger()
    # Determine current month's log file name
    now = datetime.now()
    log_file = os.path.join(LOG_FOLDER, f"logs_{now.strftime('%Y_%m')}.csv")

    # Check if the file exists and add a header if it doesn't
    file_exists = os.path.isfile(log_file)
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Date", "Time", "Locker ID", "Price"])  # Write header
        writer.writerow([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), locker_id, price])
