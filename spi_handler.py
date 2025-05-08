# spi_handler.py
#
# Raspberry Pi ↔ STM32 communication handler **with watchdog & black‑box logging**
# -----------------------------------------------------------------------------
# Features added on top of the original SPIHandler:
#   • Tracks last valid SPI traffic timestamp
#   • If >120 s of silence → pulses GPIO 14 low (100 ms) to reset the STM32
#   • Before every reset writes a line to BLACK_BOX_STM32.txt (auto‑created)
#   • If still silent another 120 s later → queues one Telegram alert
#   • When SPI resumes → flags clear and the next outage starts a new cycle
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
#  Imports & platform‑adaptive mocks
# -----------------------------------------------------------------------------
try:
    import spidev          # SPI library (real Pi)
    import lgpio           # Raspberry Pi 5 GPIO library
except ImportError:
    # ---------------- MOCKS for development/testing on non‑Pi -----------------
    class _MockSpiDev:
        def open(self, bus, device):
            print(f"[MOCK SPI] open({bus}, {device})")
        def xfer2(self, data):
            print(f"[MOCK SPI] xfer2({data})")
            return [0x00] * len(data)
        def close(self):
            print("[MOCK SPI] close()")
    spidev = type("SpiDevHolder", (), {"SpiDev": _MockSpiDev})()

    class _MockLgpio:
        @staticmethod
        def gpiochip_open(chip):
            print(f"[MOCK GPIO] gpiochip_open({chip})")
            return "mock_chip"
        @staticmethod
        def gpio_claim_input(chip, pin):
            print(f"[MOCK GPIO] gpio_claim_input({chip}, {pin})")
        @staticmethod
        def gpio_claim_output(chip, pin, level):
            print(f"[MOCK GPIO] gpio_claim_output({chip}, {pin}, level={level})")
        @staticmethod
        def gpio_read(chip, pin):
            return 0
        @staticmethod
        def gpio_write(chip, pin, value):
            print(f"[MOCK GPIO] gpio_write({chip}, {pin}, {value})")
        @staticmethod
        def gpiochip_close(chip):
            print(f"[MOCK GPIO] gpiochip_close({chip})")
    lgpio = _MockLgpio
# -----------------------------------------------------------------------------

import threading
import time
import datetime
from utils import interpret_and_notify


class SPIHandler:
    """SPI + GPIO handler with a silence watchdog and reset/alert/black‑box logic."""

    # ------------------- constants ------------------------------
    _TIMEOUT_SEC = 120            # Silence threshold (2 minutes)
    _RESET_PULSE_SEC = 2        # 100 ms active‑low pulse
    _CHECK_EVERY_SEC = 5          # Watchdog poll interval
    _RESET_GPIO_PIN = 14          # NRST line of STM32 (active‑low)
    _INTERRUPT_PIN = 17           # STM32 → Pi interrupt pin
    _BLACKBOX_PATH = "BLACK_BOX_STM32.txt"

    # ------------------- constructor ---------------------------
    def __init__(self, app, bot_queue, bus=0, device=0, speed_hz=1_600_000):
        self.app = app
        self.bot_queue = bot_queue

        # SPI init ------------------------------------------------
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(bus, device)
            self.spi.max_speed_hz = speed_hz
            self.spi.mode = 0  # SPI mode‑0
            print("SPIHandler: SPI initialised (mode 0, 1.6 MHz).")
        except Exception as e:
            print(f"SPIHandler: Failed to initialise SPI – {e}")
            self.spi = None

        # GPIO init -----------------------------------------------
        try:
            self.chip = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_input(self.chip, self._INTERRUPT_PIN)
            lgpio.gpio_claim_output(self.chip, self._RESET_GPIO_PIN, 1)  # keep NRST high
            print("SPIHandler: GPIO initialised (interrupt 17, reset 14).")
        except Exception as e:
            print(f"SPIHandler: Failed to initialise GPIO – {e}")
            self.chip = None

        # Runtime flags -------------------------------------------
        self.last_spi_time = time.time()
        self.reset_attempted = False
        self.alert_sent = False

        # Thread‑safety
        self.lock = threading.Lock()
        self.running = True

        # GPIO monitor thread
        self.gpio_thread = threading.Thread(target=self._monitor_gpio, daemon=True)
        self.gpio_thread.start()
        # Watchdog thread
        self.watchdog_thread = threading.Thread(target=self._spi_watchdog, daemon=True)
        self.watchdog_thread.start()

    # ------------------------------------------------------------------
    # Public high‑level helpers (kept from original code)
    # ------------------------------------------------------------------
    def send_command(self, command, data):
        """Thread‑safe generic SPI command sender."""
        if not self.spi:
            print("SPIHandler: SPI not initialised.")
            return
        try:
            with self.lock:
                packet = [command] + data
                print(f"SPIHandler: Sending command {packet}")
                self.spi.xfer2(packet)
        except Exception as e:
            print(f"SPIHandler: Error during SPI transfer – {e}")

    def set_led_color(self, locker_number, red, green, blue, mode=0xFF):
        self.send_command(0x01, [locker_number, red, green, blue, mode])

    def open_locker(self, locker_number):
        self.send_command(0x03, [locker_number, 0xFF, 0xFF, 0xFF, 0xFF])

    def set_price(self, locker_number, price):
        cents = int(price)
        self.send_command(0x02, [locker_number, (cents >> 8) & 0xFF, cents & 0xFF, 0xFF, 0xFF])

    # ------------------------------------------------------------------
    # GPIO interrupt monitoring
    # ------------------------------------------------------------------
    def _monitor_gpio(self):
        print("SPIHandler: GPIO monitor thread started.")
        last_state = lgpio.gpio_read(self.chip, self._INTERRUPT_PIN)
        while self.running:
            state = lgpio.gpio_read(self.chip, self._INTERRUPT_PIN)
            if state != last_state:
                print(f"GPIO {self._INTERRUPT_PIN} toggled – reading SPI.")
                self._send_dummy_and_read()
                last_state = state
            time.sleep(0.1)

    # ------------------------------------------------------------------
    # Dummy exchange (triggered by interrupt)
    # ------------------------------------------------------------------
    def _send_dummy_and_read(self):
        if not self.spi:
            return
        dummy = [0xFF] * 6
        try:
            with self.lock:
                self.spi.xfer2(dummy)            # phase‑1 (don’t care)
                time.sleep(0.1)
                response = self.spi.xfer2([0x00] * 6)  # phase‑2 (read)
            print(f"SPIHandler: SPI response {response}")

            if response and response[0] == 0xF2:
                print("SPIHandler: Reset command (0xF2) detected – "
                    "waiting 2s then resetting STM32.")
                time.sleep(2)
                self._reset_stm32()
            interpret_and_notify(self.app, response, self.bot_queue)
            # activity bookkeeping
            self.last_spi_time = time.time()
            if self.reset_attempted:
                self.reset_attempted = False
                self.alert_sent = False
        except Exception as e:
            print(f"SPIHandler: Error during SPI communication – {e}")

    # ------------------------------------------------------------------
    # Watchdog thread
    # ------------------------------------------------------------------
    def _spi_watchdog(self):
        print("SPIHandler: Watchdog thread started.")
        while self.running:
            time.sleep(self._CHECK_EVERY_SEC)
            silent_for = time.time() - self.last_spi_time
            if silent_for > self._TIMEOUT_SEC:
                if not self.reset_attempted:
                    self._log_reset_event()
                    self._reset_stm32()
                    self.reset_attempted = True
                    continue  # allow another timeout period before alerting
                if self.reset_attempted and not self.alert_sent:
                    self._send_stm32_silent_alert()
                    self.alert_sent = True

    # ------------------------- reset helpers -------------------
    def _reset_stm32(self):
        print("SPIHandler: Pulsing NRST low for reset.")
        try:
            lgpio.gpio_write(self.chip, self._RESET_GPIO_PIN, 0)
            time.sleep(self._RESET_PULSE_SEC)
            lgpio.gpio_write(self.chip, self._RESET_GPIO_PIN, 1)
        except Exception as e:
            print(f"SPIHandler: Failed to pulse reset pin – {e}")

    def _log_reset_event(self):
        try:
            ts = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
            line = f"{ts} – Watchdog reset: no SPI for {self._TIMEOUT_SEC}s\n"
            with open(self._BLACKBOX_PATH, "a", encoding="utf-8") as f:
                f.write(line)
            print(f"SPIHandler: Logged reset event to {self._BLACKBOX_PATH}.")
        except Exception as e:
            print(f"SPIHandler: Failed to write black‑box entry – {e}")

    def _send_stm32_silent_alert(self):
        msg = {
            "chat_id": None,
            "text": "❗️ STM32 has not sent an SPI packet for over two minutes (after reset)."
        }
        try:
            self.bot_queue.put(msg)
            print("SPIHandler: Telegram alert queued.")
        except Exception as e:
            print(f"SPIHandler: Failed to queue Telegram alert – {e}")

    # ------------------------- teardown -----------------------
    def close(self):
        self.running = False
        try:
            self.gpio_thread.join()
            self.watchdog_thread.join()
        except RuntimeError:
            pass
        try:
            if self.spi:
                self.spi.close()
            if self.chip:
                lgpio.gpiochip_close(self.chip)
            print("SPIHandler: Cleaned up resources.")
        except Exception as e:
            print(f"SPIHandler: Cleanup failed – {e}")
