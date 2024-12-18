import serial, io, time, sys, os

class MDBHandler:
    VEND_TIMEOUT = 10  # Timeout for vending operations in seconds.

    def __init__(self, port="/dev/ttyACM0", debug=False):
        self.port = port
        self.debug = debug
        self.ser = None
        self.sio = None

    def init_serial(self):
        """Initialize the serial port."""
        try:
            self.ser = serial.Serial(port=self.port, baudrate=115200, timeout=1)
            self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
            time.sleep(1)  # Stabilize connection
            if self.debug:
                print("Serial port initialized.")
        except Exception as e:
            print(f"Serial initialization error: {e}")
            raise

    def initserial(self):
        """Initialize serial port."""
        self.ser = serial.Serial(port=self.port, baudrate=115200, timeout=1)
        self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
        time.sleep(1)  # Allow stabilization
        if self.debug:
            print("Serial port initialized.")


    def end_comunication(self):
        """Cleanly close the serial communication."""
        self.write2Serial("D,READER,0")  # Disable the reader
        self.write2Serial("D,0")         # Disable the master
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port closed.")



    def write2Serial(self, message):
        """Write a message to the serial port."""
        self.sio.write(message + "\n")
        self.sio.flush()

    def readNWait(self):
        """Read serial response with retries."""
        for i in range(5):  # Wait for up to 500ms
            buf = self.sio.readline()
            if self.debug:
                print(f"Read: {buf}")
            if len(buf) > 0:
                break
            time.sleep(0.1)
        return buf


    def writeNReadLn(self, message):
        """Send and read response."""
        if self.debug:
            print(f"Sending: {message}")
        self.sio.write(message + "\n")
        self.sio.flush()
        return self.readNWait()

    def init_devices(self):
        """Initialize MDB master and slave devices."""
        res = self.writeNReadLn("D,2")  # Start in Direct Vend mode
        if 'D,ERR,"cashless master is on"' in res:
            print("Restarting cashless device...")
            self.write2Serial("D,0")  # Restart the master
            self.write2Serial("D,2")  # Send D,2 command again
            res = self.readNWait()

        # Wait for the slave device to send STATUS = INIT
        while 'd,STATUS,INIT' not in res:
            print("Waiting for STATUS = INIT. Please enable the reader...")
            res = self.readNWait()
        
        # Enable the reader and wait for STATUS = IDLE
        self.write2Serial("D,READER,1")  # Send enable reader command
        while 'd,STATUS,IDLE' not in res:
            print("Waiting for STATUS = IDLE...")
            res = self.readNWait()
        
        if self.debug:
            print("Slave device is IDLE and ready.")


    def detect_direct_vend(self, amount, product):
        """Check for direct vend support."""
        response = self.writeNReadLn(f"D,REQ,{amount},{product}")
        if 'd,ERR,"-1"' in response:
            return False
        if 'd,STATUS,VEND' in response:
            return response
        return None

    def normal_vend(self, amount, product):
        """Fallback for normal vend."""
        print("Please insert payment media...")
        response = self.readNWait()
        if 'd,STATUS,CREDIT,' in response:
            credit = float(response.split(",")[-1])
            if credit >= float(amount):
                response = self.writeNReadLn(f"D,REQ,{amount},{product}")
                if 'd,STATUS,VEND' in response:
                    print("Transaction Success.")
                    return True
        print("Insufficient credit or failure.")
        return False

    def cleanup(self):
        """Close serial port."""
        if self.ser:
            self.ser.close()
            print("Serial port closed.")

    def cancelTransaction(self):
        """Cancel the ongoing transaction."""
        res = self.writeNReadLn("D,REQ,-1")
        if self.debug:
            print(f"Transaction cancelled: {res}")

    def endTransaction(self, amount, product, response):
        """Handle the end of a successful transaction."""
        print("Finalizing transaction...")
        if "SUCCESS" in response or "d,STATUS,RESULT,1" in response:
            print(f"Transaction SUCCESS: {amount}€ for product {product}")
            self.writeNReadLn("D,END")
        elif "FAILED" in response or "d,STATUS,RESULT,-1" in response:
            raise ValueError("Transaction Denied by cashless device!")
        else:
            raise ValueError("Transaction Failed!")


