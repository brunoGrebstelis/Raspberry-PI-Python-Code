# Try to import spidev for Raspberry Pi SPI communication
try:
    import spidev  # Import the SPI library for Raspberry Pi
    SpiDev = spidev.SpiDev  # Assign SpiDev to the spidev class
except ImportError:
    # Mock implementation of SpiDev for development/testing on Windows
    class SpiDev:
        def open(self, bus, device):
            print(f"Mock SPI: Opened bus {bus}, device {device}")

        def xfer2(self, data):
            print(f"Mock SPI: Transferred data {data}")
            return data  # Simulate an echo response

        def close(self):
            print("Mock SPI: Closed connection")

# Define the SPIHandler class
class SPIHandler:
    def __init__(self, bus=0, device=0, speed_hz=500000):
        """
        Initialize the SPI communication.
        :param bus: SPI bus (default is 0).
        :param device: SPI device (default is 0).
        :param speed_hz: Clock speed in Hz (default is 500 kHz).
        """
        self.spi = SpiDev()  # Use either the real or mock SpiDev class
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0  # SPI Mode 0 (adjust if necessary)

    def send_command(self, command, data):
        """
        Send a command with data to STM32 over SPI.
        :param command: Command identifier (1 byte).
        :param data: List of data bytes to send.
        """
        packet = [command] + data  # Combine command and data into a single list
        self.spi.xfer2(packet)  # Transfer the packet over SPI

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
        data = [locker_number, (price_in_cents >> 8) & 0xFF, price_in_cents & 0xFF]  # Split price into 2 bytes
        self.send_command(command, data)

    def close(self):
        """Close the SPI connection."""
        self.spi.close()
