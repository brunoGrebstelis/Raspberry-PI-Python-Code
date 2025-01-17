# utils.py
import json
import os
import csv
import sqlite3
from datetime import datetime, timedelta
from collections import Counter
import matplotlib.pyplot as plt

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

from admin_windows import InformationWindow
from collections import defaultdict, Counter



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


def parse_period(period: str):
    """
    Convert the user-friendly 'period' (e.g. "This Month", "2025-01", "2025-01-01 to 2025-01-05")
    into (start_date, end_date).
    
    Returns (start_date, end_date) as datetime objects, or None if we can't interpret.
    """

    now = datetime.now()
    
    # Manual range "YYYY-MM-DD to YYYY-MM-DD"?
    if " to " in period:
        parts = period.split(" to ")
        if len(parts) == 2:
            try:
                start_dt = datetime.strptime(parts[0], "%Y-%m-%d")
                end_dt = datetime.strptime(parts[1], "%Y-%m-%d")
                if end_dt < start_dt:
                    # Swap if user wrote them backwards
                    start_dt, end_dt = end_dt, start_dt
                return (start_dt, end_dt)
            except ValueError:
                return None
    p_lower = period.lower()

    # "today"
    if p_lower == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt  # same day
        return (start_dt, end_dt)

    # "yesterday"
    if p_lower == "yesterday":
        yest = now - timedelta(days=1)
        start_dt = yest.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt
        return (start_dt, end_dt)

    # "this month"
    if p_lower == "this month":
        # 1st day of current month
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # end of this month
        # approach: next month day=1 minus 1 day
        if start_dt.month == 12:
            next_month = start_dt.replace(year=start_dt.year + 1, month=1, day=1)
        else:
            next_month = start_dt.replace(month=start_dt.month + 1, day=1)
        end_dt = next_month - timedelta(days=1)
        return (start_dt, end_dt)

    # "last month"
    if p_lower == "last month":
        # We subtract 1 month from 'now'
        # but let's do it from the 1st of this month
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_end = first_this_month - timedelta(days=1)  # This becomes last day of previous month
        # Now we find the start of that last month
        start_dt = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = last_month_end
        return (start_dt, end_dt)

    # "this year"
    if p_lower == "this year":
        start_dt = datetime(now.year, 1, 1)
        end_dt = datetime(now.year, 12, 31, 23, 59, 59)
        return (start_dt, end_dt)

    # "last year"
    if p_lower == "last year":
        ly = now.year - 1
        start_dt = datetime(ly, 1, 1)
        end_dt = datetime(ly, 12, 31, 23, 59, 59)
        return (start_dt, end_dt)

    # "total" or "then" => interpret as all-time
    if p_lower in ["total", "then"]:
        # earliest possible date
        # or you might look in DB for earliest record
        start_dt = datetime(2000, 1, 1)
        end_dt = now  # up to current day
        return (start_dt, end_dt)

    # If it's exactly YYYY => entire year
    if len(period) == 4 and period.isdigit():
        year_int = int(period)
        start_dt = datetime(year_int, 1, 1)
        end_dt = datetime(year_int, 12, 31, 23, 59, 59)
        return (start_dt, end_dt)

    # If it's YYYY-MM => parse month
    if len(period) == 7:
        try:
            year_str, month_str = period.split("-")
            year_int = int(year_str)
            month_int = int(month_str)
            start_dt = datetime(year_int, month_int, 1)
            # next month:
            if month_int == 12:
                next_month = start_dt.replace(year=year_int + 1, month=1)
            else:
                next_month = start_dt.replace(month=month_int + 1)
            end_dt = next_month - timedelta(days=1)
            return (start_dt, end_dt)
        except:
            return None

    # If it's YYYY-MM-DD => parse day
    if len(period) == 10:
        try:
            day_dt = datetime.strptime(period, "%Y-%m-%d")
            return (day_dt, day_dt)
        except ValueError:
            return None

    # If all else fails, can't interpret
    return None


def group_sales_data(rows, start_dt, end_dt):
    """
    Groups sales data based on the specified period.

    Args:
        rows (list): List of tuples containing (date_str, time_str, locker_id, price).
        start_dt (datetime): Start datetime object.
        end_dt (datetime): End datetime object.

    Returns:
        tuple: (grouped_sums, locker_earnings, grouping, group_sales_counts, locker_sales_counts)
            - grouped_sums (dict): {group_key: total_earnings}
            - locker_earnings (dict): {locker_id: total_money}
            - grouping (str): The grouping level ('hour', 'day', 'month', 'year')
            - group_sales_counts (dict): {group_key: total_sales_count}
            - locker_sales_counts (dict): {locker_id: total_sales_count}
    """
    diff_days = (end_dt - start_dt).days

    # Decide grouping
    if diff_days <= 3:
        grouping = "hour"
    elif diff_days <= 30:
        grouping = "day"
    elif diff_days <= 365:
        grouping = "month"
    else:
        grouping = "year"

    grouped_sums = defaultdict(float)
    locker_earnings = defaultdict(float)
    group_sales_counts = defaultdict(int)       # New: Count of sales per group
    locker_sales_counts = defaultdict(int)      # New: Count of sales per locker

    for (sale_date_str, sale_time_str, locker_id, price) in rows:
        # Parse the sale datetime
        try:
            sale_dt = datetime.strptime(f"{sale_date_str} {sale_time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Handle unexpected time format
            sale_dt = datetime.strptime(sale_date_str, "%Y-%m-%d")  # Fallback to date only

        if grouping == "hour":
            # Group by each hour within the day
            group_key = sale_dt.strftime("%Y-%m-%d %H:00")
        elif grouping == "day":
            group_key = sale_dt.strftime("%Y-%m-%d")
        elif grouping == "month":
            group_key = sale_dt.strftime("%Y-%m")
        else:  # "year"
            group_key = sale_dt.strftime("%Y")

        grouped_sums[group_key] += price
        locker_earnings[locker_id] += price
        group_sales_counts[group_key] += 1               # Increment sales count for the group
        locker_sales_counts[locker_id] += 1              # Increment sales count for the locker

    return grouped_sums, locker_earnings, grouping, group_sales_counts, locker_sales_counts





def generate_sales_report(period: str):
    """
    Generates a sales report based on the specified period.
    
    Returns:
        Tuple containing:
        - report_text (str): The textual summary of the sales report.
        - line_chart_path (str): File path to the generated line chart image.
        - pie_chart_path (str): File path to the generated pie chart image.
    """
    # Utility function to remove ".00" if present
    def remove_trailing_zeros(value: float) -> str:
        formatted = f"{value:,.2f}"  # Keep thousands separator
        # Strip trailing zeros and a trailing dot if it becomes leftover
        formatted = formatted.rstrip('0').rstrip('.')
        return formatted

    date_range = parse_period(period)
    if not date_range:
        return (f"Could not interpret period: {period}", None, None)

    (start_dt, end_dt) = date_range

    # 2) Query logs in that range
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Modified SELECT query to include 'time'
    query = """
        SELECT date, time, locker_id, price
        FROM logs
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC, time ASC
    """
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    cursor.execute(query, (start_str, end_str))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return (f"No logs found from {start_str} to {end_str} ({period}).", None, None)

    # 3) Group sums and count sales
    grouped_sums, locker_earnings, grouping, group_sales_counts, locker_sales_counts = group_sales_data(rows, start_dt, end_dt)
    # Total earnings and total purchases
    total_earnings = sum(grouped_sums.values())
    total_purchases = sum(group_sales_counts.values())

    # Sort the group keys
    sorted_groups = sorted(grouped_sums.items(), key=lambda x: x[0])
    # Top 3 groups by sum
    top_3 = sorted(grouped_sums.items(), key=lambda x: x[1], reverse=True)[:3]
    # Get corresponding sales counts for top 3 groups
    top_3_with_counts = [(g, v, group_sales_counts[g]) for (g, v) in top_3]

    # **Change Starts Here: Sort Lockers by Earnings Instead of Sales Counts**
    # Sort lockers by total earnings in descending order
    sorted_lockers_by_earnings = sorted(locker_earnings.items(), key=lambda x: x[1], reverse=True)
    # Select Top 3 Lockers based on earnings
    top_3_lockers = sorted_lockers_by_earnings[:3]
    # **Change Ends Here**

    # 4) Build text summary without emojis
    lines = []
    lines.append(f"Sales Report for {period}")
    lines.append(f"Date Range: {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}")
    lines.append(f"Total Earnings: €{remove_trailing_zeros(total_earnings)}")
    lines.append(f"Total Purchases: {total_purchases}")
    lines.append("")
    lines.append(f"Grouping by: {grouping.capitalize()}")
    lines.append("Top 3 Groups (by earnings):")
    for (g, val, count) in top_3_with_counts:
        lines.append(f"   • {g}: €{remove_trailing_zeros(val)} ({count})")
    lines.append("")
    lines.append("Top 3 Lockers (by earnings):")  # Updated Title
    for (locker_id, earnings) in top_3_lockers:
        sales_count = locker_sales_counts.get(locker_id, 0)
        lines.append(f"   • Locker {locker_id}: €{remove_trailing_zeros(earnings)} ({sales_count})")
    report_text = "\n".join(lines)

    # 5) Build charts
    # -- (a) Line Chart --
    x_vals = [kv[0] for kv in sorted_groups]
    y_vals = [kv[1] for kv in sorted_groups]
    sales_counts = [group_sales_counts[kv[0]] for kv in sorted_groups]

    plt.figure(figsize=(12, 6))
    plt.plot(x_vals, y_vals, marker='o', linestyle='-', color='blue', label='Earnings (€)')
    plt.xlabel(grouping.capitalize())
    plt.ylabel("Earnings (€)")
    plt.title(f"Earnings Over Time: {period}")
    plt.xticks(rotation=45, ha='right')
    plt.grid(True)

    # Make the top maximum value a bit larger so annotations are not cut off
    if y_vals:
        max_y = max(y_vals)
        plt.ylim(top=max_y * 1.1)

    # Annotate each point with earnings and number of sales (in one line)
    for x, y, count in zip(x_vals, y_vals, sales_counts):
        annotation_text = f"€{remove_trailing_zeros(y)}({count})"
        plt.annotate(annotation_text, (x, y), textcoords="offset points", xytext=(0,10), ha='center', fontsize=8)

    plt.tight_layout()
    line_chart_path = "charts/line_chart.png"
    plt.savefig(line_chart_path)
    plt.close()

    # -- (b) Pie Chart based on number of sales --
    # Labels include locker ID, earnings, and number of sales without the word "sales"
    labels = []
    values = []
    for (locker_id, sales_count) in locker_sales_counts.items():
        earnings = locker_earnings.get(locker_id, 0.0)
        labels.append(f"L{locker_id}: €{remove_trailing_zeros(earnings)}({sales_count})")
        values.append(sales_count)

    # If you only want to include the top 3 lockers in the pie chart:
    # Uncomment the following lines and comment out the above for-loop
    # labels = []
    # values = []
    # for (locker_id, earnings) in top_3_lockers:
    #     sales_count = locker_sales_counts.get(locker_id, 0)
    #     labels.append(f"Locker {locker_id}: €{remove_trailing_zeros(earnings)} ({sales_count})")
    #     values.append(sales_count)

    plt.figure(figsize=(8, 8))
    if sum(values) == 0:
        plt.text(0.5, 0.5, "No sales", horizontalalignment='center', verticalalignment='center', fontsize=12)
    else:
        plt.pie(values, labels=labels, autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else '', startangle=140)
        plt.title(f"Locker Sales Distribution: {period}")
    pie_chart_path = "charts/pie_chart.png"
    plt.savefig(pie_chart_path)
    plt.close()

    return (report_text, line_chart_path, pie_chart_path)





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
    Loads lockers.json and returns a beautifully formatted string listing each locker.
    🟢 = Locker with a flower inside
    🔴 = Empty locker
    🟡 = Reserved locker
    """
    data = load_locker_data()  # This function is already in utils.py
    lines = ["🔓 *Locker Status:*"]

    for locker_id_str, locker_dict in data.items():
        price = locker_dict.get("price", 0)
        status = locker_dict.get("status", True)
        locker_pin = locker_dict.get("locker_pin", -1)

        if locker_pin != -1:
            # Locker is reserved
            lines.append(f"🟡 Locker {locker_id_str}: {price}€ (Reserved)")
        else:
            # Follow the original logic for status
            if status:
                # Locker has a flower
                lines.append(f"🟢 Locker {locker_id_str}: {price}€ (Full)")
            else:
                # Locker is empty
                lines.append(f"🔴 Locker {locker_id_str}: {price}€ (Empty)")

    return "\n".join(lines)





def interpret_and_notify(data):

    if not isinstance(data, (bytes, bytearray)) or len(data) != 5:
        print("Invalid input: Expected a 5-byte sequence.")

    command = data[0]
    byte2 = data[1]
    byte3 = data[2]



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


        

