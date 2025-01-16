# Try to import spidev and lgpio for Raspberry Pi SPI and GPIO communication
try:
    import spidev  # SPI library
    import lgpio  # GPIO library for Raspberry Pi 5 compatibility
except ImportError:
    # Mock implementations for development/testing on non-Raspberry Pi systems
    class SpiDev:
        def open(self, bus, device):
            print(f"Mock SPI: Opened bus {bus}, device {device}")

        def xfer2(self, data):
            print(f"Mock SPI: Transferred data {data}")
            return [0x00] * len(data)  # Simulate an all-zero response

        def close(self):
            print("Mock SPI: Closed connection")

    spidev = SpiDev()  # Use mock SpiDev

    class lgpio:
        @staticmethod
        def gpiochip_open(chip):
            print(f"Mock GPIO: Opened GPIO chip {chip}")
            return "mock_chip"

        @staticmethod
        def gpio_claim_input(chip, pin):
            print(f"Mock GPIO: Claimed pin {pin} as input")

        @staticmethod
        def gpio_read(chip, pin):
            return 0  # Simulate GPIO low state

        @staticmethod
        def gpiochip_close(chip):
            print("Mock GPIO: Closed GPIO chip")

        @staticmethod
        def gpio_write(chip, pin, value):
            print(f"Mock GPIO: Wrote {value} to pin {pin}")

# SPIHandler class
import threading
import time
from utils import interpret_and_notify

class SPIHandler:
    def __init__(self, bus=0, device=0, speed_hz=1600000):
        # Initialize SPI
        try:
            self.spi = spidev.SpiDev()  # Use spidev
            self.spi.open(bus, device)
            self.spi.max_speed_hz = speed_hz
            self.spi.mode = 0  # SPI Mode 0
            print("SPIHandler: SPI initialized successfully.")
        except Exception as e:
            print(f"SPIHandler: Failed to initialize SPI - {e}")
            self.spi = None

        # Initialize GPIO
        try:
            self.interrupt_pin = 17
            self.chip = lgpio.gpiochip_open(0)  # Open GPIO chip 0
            lgpio.gpio_claim_input(self.chip, self.interrupt_pin)  # Set interrupt_pin as input
            print("SPIHandler: GPIO initialized successfully.")
        except Exception as e:
            print(f"SPIHandler: Failed to initialize GPIO - {e}")
            self.chip = None

        # Initialize threading lock
        self.lock = threading.Lock()

        # Start GPIO monitoring thread
        self.running = True
        self.gpio_thread = threading.Thread(target=self.monitor_gpio)
        self.gpio_thread.daemon = True
        self.gpio_thread.start()

    def monitor_gpio(self):
        """
        Thread to monitor GPIO pin state.
        """
        print("SPIHandler: Starting GPIO monitoring thread.")
        while self.running:
            if self.chip:
                pin_state = lgpio.gpio_read(self.chip, self.interrupt_pin)
                if pin_state == 1:  # GPIO is high
                    print(f"GPIO {self.interrupt_pin} is HIGH. Sending dummy message.")
                    self.send_dummy_and_read()
            time.sleep(0.1)  # Adjust polling interval as needed

    def send_command(self, command, data):
        if not self.spi:
            print("SPIHandler: SPI not initialized.")
            return
        try:
            packet = [command] + data
            self.spi.xfer2(packet)
        except Exception as e:
            print(f"SPIHandler: Error during SPI transfer - {e}")

    def set_led_color(self, locker_number, red, green, blue):
        self.send_command(0x01, [locker_number, red, green, blue])

    def open_locker(self, locker_number):
        self.send_command(0x03, [locker_number, 0xFF, 0xFF, 0xFF])

    def set_price(self, locker_number, price):
        price_in_cents = int(price  )
        self.send_command(0x02, [locker_number, (price_in_cents >> 8) & 0xFF, price_in_cents & 0xFF, 0x00])

    def send_dummy_and_read(self):
        if not self.spi:
            print("SPIHandler: SPI not initialized.")
            return
        dummy_message = [0xFF] * 5
        try:
            with self.lock:
                print("Sending dummy message...")
                response = self.spi.xfer2(dummy_message)  # Send dummy message
                time.sleep(0.1)
                response = self.spi.xfer2([0x00] * 5)  # Receive 5 bytes
                print(f"SPI Response: {response}")
                interpret_and_notify(response)
        except Exception as e:
            print(f"SPIHandler: Error during SPI communication - {e}")

    def close(self):
        """
        Clean up SPI and GPIO resources.
        """
        self.running = False  # Stop the GPIO monitoring thread
        self.gpio_thread.join()  # Ensure the thread exits cleanly
        try:
            if self.spi:
                self.spi.close()
            if self.chip:
                lgpio.gpiochip_close(self.chip)
            print("SPIHandler: Cleaned up resources.")
        except Exception as e:
            print(f"SPIHandler: Failed to clean up resources - {e}")
