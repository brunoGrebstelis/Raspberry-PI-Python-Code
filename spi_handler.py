# Try to import spidev and lgpio for Raspberry Pi SPI and GPIO communication
try:
    import spidev  # SPI library
    import lgpio   # GPIO library for Raspberry Pi 5 compatibility
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
    def __init__(self, app, bot_queue, bus=0, device=0, speed_hz=1600000):
        self.app = app 
        self.bot_queue = bot_queue
        
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
        last_pin_state = lgpio.gpio_read(self.chip, self.interrupt_pin)
        while self.running:
            if self.chip:
                pin_state = lgpio.gpio_read(self.chip, self.interrupt_pin)
                # If the pin state changes (e.g. goes HIGH),
                # we send a dummy message to read from the slave
                if pin_state != last_pin_state:  
                    print(f"GPIO {self.interrupt_pin} changed state. Sending dummy message.")
                    self.send_dummy_and_read()
                    last_pin_state = pin_state
            time.sleep(0.1)  # Adjust polling interval as needed

    def send_command(self, command, data):
        """
        Send a command to the SPI slave with the provided data.
        Now protected by self.lock so it cannot overlap with send_dummy_and_read().
        """
        if not self.spi:
            print("SPIHandler: SPI not initialized.")
            return
        try:
            with self.lock:  # Acquire the lock so no other SPI method can run at the same time
                packet = [command] + data
                print(f"SPIHandler: Sending command {packet}")
                self.spi.xfer2(packet)
        except Exception as e:  
            print(f"SPIHandler: Error during SPI transfer - {e}")

    def set_led_color(self, locker_number, red, green, blue, mode=0xFF):
        """
        Example convenience method that calls send_command()
        to set LED color on a specific locker.
        """
        self.send_command(0x01, [locker_number, red, green, blue, mode])

    def open_locker(self, locker_number):
        """
        Example convenience method that calls send_command()
        to unlock a locker.
        """
        self.send_command(0x03, [locker_number, 0xFF, 0xFF, 0xFF, 0xFF])

    def set_price(self, locker_number, price):
        """
        Example convenience method that calls send_command()
        to set a price for a locker.
        """
        price_in_cents = int(price)
        self.send_command(0x02, [
            locker_number,
            (price_in_cents >> 8) & 0xFF,
            price_in_cents & 0xFF,
            0xFF,
            0xFF
        ])

    def send_dummy_and_read(self):
        """
        Sends a dummy message and then reads the response.
        Protected by self.lock so it cannot overlap with send_command().
        """
        if not self.spi:
            print("SPIHandler: SPI not initialized.")
            return
        dummy_message = [0xFF] * 6
        try:
            with self.lock:
                print("SPIHandler: Sending dummy message...")
                # First transaction (dummy out)
                response = self.spi.xfer2(dummy_message)
                time.sleep(0.1)
                # Second transaction to read
                response = self.spi.xfer2([0x00] * 6)
                print(f"SPIHandler: SPI Response: {response}")
                interpret_and_notify(self.app, response, self.bot_queue)
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
