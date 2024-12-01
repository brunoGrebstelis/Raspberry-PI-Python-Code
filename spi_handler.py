# Try to import spidev and RPi.GPIO for Raspberry Pi SPI communication
try:
    import spidev  # SPI library
    import RPi.GPIO as GPIO  # GPIO library
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

    class GPIO:
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        PUD_DOWN = "PUD_DOWN"
        RISING = "RISING"

        @staticmethod
        def setmode(mode):
            print(f"Mock GPIO: Set mode {mode}")

        @staticmethod
        def setup(pin, mode, pull_up_down=None):
            print(f"Mock GPIO: Setup pin {pin} as {mode} with pull {pull_up_down}")

        @staticmethod
        def add_event_detect(pin, edge, callback=None):
            print(f"Mock GPIO: Added event detect on pin {pin} for edge {edge}")

        @staticmethod
        def cleanup():
            print("Mock GPIO: Cleanup")

        @staticmethod
        def input(pin):
            return 0

# SPIHandler class
import threading
import time

# Define the SPIHandler class
class SPIHandler:
    def __init__(self, bus=0, device=0, speed_hz=1600000):
        """
        Initialize the SPI communication.
        :param bus: SPI bus (default is 0).
        :param device: SPI device (default is 0).
        :param speed_hz: Clock speed in Hz (default is 500 kHz).
        """

        # Initialize SPI
        self.spi = spidev.SpiDev()  # Use either the real or mock SpiDev class
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0  # SPI Mode 0

        try:


            # Initialize GPIO
            self.interrupt_pin = 17
            GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
            GPIO.setup(self.interrupt_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            # Add interrupt detection
            GPIO.add_event_detect(self.interrupt_pin, GPIO.RISING, callback=self.handle_interrupt)

            # Lock for thread safety
            self.lock = threading.Lock()
            print("SPIHandler: Initialized successfully.")
        except Exception as e:
            print(f"SPIHandler: Failed to initialize - {e}")
            self.spi = None  # Ensure SPI object exists
            self.lock = None
        



    def send_command(self, command, data):
        """
        Send a command with data to STM32 over SPI.
        :param command: Command identifier (1 byte).
        :param data: List of data bytes to send.
        """
        
        #GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
        #CS_PIN = 8  # Update with the correct CS pin (e.g., GPIO 8)
        #GPIO.setup(CS_PIN, GPIO.OUT)  # Set the CS pin as an output
        #self.CS_PIN = CS_PIN  # Save the CS pin for later use
        
        packet = [command] + data  # Combine command and data into a single list
        #GPIO.output(CS_PIN, GPIO.LOW)  # Pull CS LOW
        self.spi.xfer2(packet)  # Transfer the packet over SPI
        #GPIO.output(CS_PIN, GPIO.HIGH)  # Pull CS HIGH
        time.sleep(0.05)  # 50 ms delay
        

    def set_led_color(self, locker_number, red, green, blue):
        """
        Send the LED color command to STM32.
        :param locker_number: Locker number (1 byte).
        :param red: Red color intensity (0-255).
        :param green: Green color intensity (0-255).
        :param blue: Blue color intensity (0-255).
        """
        command = 0x01  # Command for LED COLOR
        data = [locker_number, red, green, blue]
        self.send_command(command, data)

    def set_price(self, locker_number, price):
        """
        Send the PRICE command to STM32.
        :param locker_number: Locker number (1 byte).
        :param price: Price in euros (float, converted to cents as an integer).
        """
        command = 0x02  # Command for PRICE
        price_in_cents = int(price * 100)  # Convert price to cents
        data = [locker_number, (price_in_cents >> 8) & 0xFF, price_in_cents & 0xFF, 0x00]  # Split price into 2 bytes
        self.send_command(command, data)



    def send_dummy_and_read(self):  # NEW FUNCTIONALITY
        """
        Send a dummy message and read 5 bytes from SPI.
        """
        dummy_message = [0xFF] * 5  # Dummy message (5 bytes of 0xFF)
        if self.spi:
            try:
                with self.lock:
                    self.spi.xfer2(dummy_message)  # Send dummy message
                    response = self.spi.xfer2([0x00] * 5)  # Receive 5 bytes
                print(f"SPI Response: {response}")
            except Exception as e:
                print(f"SPIHandler: Error during SPI communication - {e}")
        else:
            print("SPIHandler: SPI not initialized.")

    def handle_interrupt(self, channel):  # NEW FUNCTIONALITY
        """
        Handle GPIO interrupt. Triggered when STM32 signals data availability.
        """
        print(f"Interrupt detected on GPIO {channel}. Sending dummy message.")
        self.send_dummy_and_read()

    def close(self):
        """Clean up SPI and GPIO resources."""
        try:
            if self.spi:  # Check if the SPI object is valid
                self.spi.close()  # Close the SPI connection
            GPIO.cleanup()  # Clean up GPIO resources
            print("SPIHandler: Cleaned up resources.")
        except Exception as e:
            print(f"SPIHandler: Failed to clean up resources - {e}")