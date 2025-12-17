import schedule
import time
import os
from threading import Thread
from datetime import datetime, timedelta
from utils import generate_sales_report
import subprocess
import socket

# Reuse the same connection names as the bot
WIFI_CONN_NAME = "WLAN - ZNGQXU"
ETH_CONN_NAME  = "wired connection 1"   # "" if you never want Ethernet fallback

class Scheduler:
    def __init__(self, bot_queue):
        self.bot_queue = bot_queue
        self.running = False

    def schedule_tasks(self):
        """
        Daily checks for:
          1) 10:00 => If day == 1 => generate last month's report
          2) 00:00 => If it's Jan 1 => send Happy New Year & last year's report
          3) Every 10 minutes => connectivity self-heal
        """
        schedule.every().day.at("10:00").do(self._monthly_report)
        schedule.every().day.at("00:00").do(self._yearly_report)
        schedule.every(10).minutes.do(self._periodic_connectivity_check)  # NEW

    # ------------------------ Connectivity self-heal (robust, sync) ------------------------

    def _run_cmd(self, cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True)
            # Optional debugging:
            # if p.returncode != 0:
            #     print(f"[Scheduler] CMD fail: {' '.join(map(str, cmd))} -> {p.returncode} | {p.stderr.strip()}")
            return p.returncode
        except Exception:
            return 1

    def _dns_ok(self) -> bool:
        try:
            socket.getaddrinfo("one.one.one.one", 443, proto=socket.IPPROTO_TCP)
            return True
        except Exception:
            return False

    def _default_iface(self) -> str | None:
        try:
            p = subprocess.run(["ip", "route", "get", "1.1.1.1"], capture_output=True, text=True)
            if p.returncode == 0:
                parts = p.stdout.strip().split()
                if "dev" in parts:
                    idx = parts.index("dev") + 1
                    if idx < len(parts):
                        return parts[idx]
        except Exception:
            pass
        return None

    def _ensure_network(self) -> bool:
        if self._dns_ok():
            return True

        ping_ok = (self._run_cmd(["ping", "-c", "1", "-W", "2", "1.1.1.1"]) == 0)

        # Bring links up
        if ETH_CONN_NAME:
            self._run_cmd(["nmcli", "device", "connect", "eth0"])
            self._run_cmd(["nmcli", "con", "up", ETH_CONN_NAME])

        self._run_cmd(["nmcli", "radio", "wifi", "on"])
        self._run_cmd(["nmcli", "device", "connect", "wlan0"])
        self._run_cmd(["nmcli", "con", "up", WIFI_CONN_NAME])

        # If link OK but DNS broken -> set DNS on active iface and both common ifaces, flush, set profile DNS
        if ping_ok and not self._dns_ok():
            active = self._default_iface()
            if active in ("wlan0", "eth0"):
                self._run_cmd(["resolvectl", "dns", active, "1.1.1.1", "8.8.8.8"])
            self._run_cmd(["resolvectl", "dns", "wlan0", "1.1.1.1", "8.8.8.8"])
            self._run_cmd(["resolvectl", "dns", "eth0", "1.1.1.1", "8.8.8.8"])
            self._run_cmd(["resolvectl", "flush-caches"])

            if ETH_CONN_NAME:
                self._run_cmd(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.ignore-auto-dns", "yes"])
                self._run_cmd(["nmcli", "con", "mod", ETH_CONN_NAME, "ipv4.dns", "1.1.1.1 8.8.8.8"])
            self._run_cmd(["nmcli", "con", "mod", WIFI_CONN_NAME, "ipv4.ignore-auto-dns", "yes"])
            self._run_cmd(["nmcli", "con", "mod", WIFI_CONN_NAME, "ipv4.dns", "1.1.1.1 8.8.8.8"])

        time.sleep(2)
        return self._dns_ok()

    def _periodic_connectivity_check(self):
        # Best effort heal; never throws
        self._ensure_network()
        return None

    # -----------------------------------------------------------------------------------------

    def _monthly_report(self):
        now = datetime.now()
        if now.day == 1:
            start_date, end_date = self._get_previous_month_range()
            period_label = f"{start_date} to {end_date}"
            report_text, line_chart_path, pie_chart_path = generate_sales_report(period_label)

            self.bot_queue.put({
                "chat_id": None,
                "text": report_text,
            })

            if line_chart_path and os.path.isfile(line_chart_path):
                self.bot_queue.put({
                    "chat_id": None,
                    "image_path": line_chart_path,
                    "caption": "Sales Over Time (Previous Month)",
                })

            if pie_chart_path and os.path.isfile(pie_chart_path):
                self.bot_queue.put({
                    "chat_id": None,
                    "image_path": pie_chart_path,
                    "caption": "Best Selling Lockers (Previous Month)",
                })

    def _yearly_report(self):
        now = datetime.now()
        if now.day == 1 and now.month == 1:
            self.bot_queue.put({
                "chat_id": None,
                "text": "Happy New Year! 🎉🥂",
            })

            start_date, end_date = self._get_previous_year_range()
            period_label = f"{start_date} to {end_date}"
            report_text, line_chart_path, pie_chart_path = generate_sales_report(period_label)

            self.bot_queue.put({
                "chat_id": None,
                "text": report_text,
            })

            if line_chart_path and os.path.isfile(line_chart_path):
                self.bot_queue.put({
                    "chat_id": None,
                    "image_path": line_chart_path,
                    "caption": "Sales Over Time (Previous Year)",
                })

            if pie_chart_path and os.path.isfile(pie_chart_path):
                self.bot_queue.put({
                    "chat_id": None,
                    "image_path": pie_chart_path,
                    "caption": "Best Selling Lockers (Previous Year)",
                })

    def _get_previous_month_range(self):
        today = datetime.today()
        first_of_current_month = today.replace(day=1)
        last_day_prev_month = first_of_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        return (first_day_prev_month.strftime("%Y-%m-%d"),
                last_day_prev_month.strftime("%Y-%m-%d"))

    def _get_previous_year_range(self):
        today = datetime.today()
        last_year = today.year - 1
        return (datetime(last_year, 1, 1).strftime("%Y-%m-%d"),
                datetime(last_year, 12, 31).strftime("%Y-%m-%d"))

    def start(self):
        self.running = True
        self.schedule_tasks()
        # heal once at startup so we don't wait 10 minutes
        try:
            self._periodic_connectivity_check()
        except Exception:
            pass
        Thread(target=self.run, daemon=True).start()

    def run(self):
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        self.running = False
