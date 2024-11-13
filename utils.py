# utils.py
import json
import os

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
            return json.load(f)
    except FileNotFoundError:
        return {str(i): {"locker_id": i, "price": 5.0} for i in range(1, 13)}

def save_locker_data(data):
    with open('lockers.json', 'w') as f:
        json.dump(data, f, indent=4)

def send_command(command):
    if serial_enabled and ser:
        ser.write(command.encode())
        ser.flush()
    else:
        print(f"Mock UART Command Sent: {command}")
