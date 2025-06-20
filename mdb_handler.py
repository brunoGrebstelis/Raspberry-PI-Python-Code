import serial
import io
import time
import logging
from datetime import datetime
from pathlib import Path

"""
MDBHandler – rewritten with black‑box logging
Every informational or error message is now written to
   logs/BLACK_BOX_POS.txt
Each line in that file begins with an ISO timestamp.
If you instantiate the class with debug=True the same text is also echoed to
stdout, so existing behaviour is preserved.

Only this module handles the black‑box; the separate PROGRAMM_RUNNED.txt marker
will be added in app.py / main.py once we agree on its placement.
"""

# ---------------------------------------------------------------------------
#                       black‑box log setup                                  
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "BLACK_BOX_POS.txt"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",                      # append, never overwrite
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
_logger = logging.getLogger("BLACK_BOX_POS")


# ---------------------------------------------------------------------------
#                           helper                                           
# ---------------------------------------------------------------------------

def _log(msg: str, debug_echo: bool = False):
    """Write *msg* to the black‑box file and optionally to stdout."""
    _logger.info(msg)
    if debug_echo:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {msg}")


# ---------------------------------------------------------------------------
#                             main class                                     
# ---------------------------------------------------------------------------
class MDBHandler:
    VEND_TIMEOUT = 10  # timeout for vending operations in seconds

    def __init__(self, port: str = "/dev/ttyACM0", debug: bool = False):
        self.port = port
        self.debug = debug
        self.ser = None
        self.sio = None
        _log(f"MDBHandler created for port {self.port}", self.debug)

    # ------------------- serial initialisation --------------------------- #
    def init_serial(self):
        """Preferred initialiser (kept for compatibility)."""
        try:
            self.ser = serial.Serial(port=self.port, baudrate=115200, timeout=1)
            self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
            time.sleep(1)  # stabilise connection
            _log("Serial port initialised.", self.debug)
        except Exception as e:
            _log(f"Serial initialisation error: {e}", True)
            raise

    # legacy alias – project still calls this name in some places
    initserial = init_serial

    # ------------------------ high‑level helpers ------------------------- #
    def end_comunication(self):
        """Cleanly close the serial communication."""
        self.write2Serial("D,READER,0")  # disable the reader
        self.write2Serial("D,0")         # disable the master
        if self.ser and self.ser.is_open:
            self.ser.close()
            _log("Serial port closed.", self.debug)

    def write2Serial(self, message: str):
        """Write *message* and flush."""
        self.sio.write(message + "\n")
        self.sio.flush()

    def readNWait(self):
        """Read a response line, trying for up to 500 ms."""
        for _ in range(5):
            buf = self.sio.readline()
            if self.debug:
                _log(f"Read: {buf.strip()}", True)
            if buf:
                break
            time.sleep(0.1)
        return buf

    def writeNReadLn(self, message: str):
        """Send *message* then wait for a response."""
        if self.debug:
            _log(f"Sending: {message}", True)
        self.sio.write(message + "\n")
        self.sio.flush()
        return self.readNWait()

    # -------------------- device initialisation ------------------------- #
    def init_devices(self):
        """Initialise MDB master and slave devices."""
        res = self.writeNReadLn("D,2")   # Direct‑Vend mode
        if 'D,ERR,"cashless master is on"' in res:
            _log("Restarting cashless device...", self.debug)
            self.write2Serial("D,0")
            self.write2Serial("D,2")
            res = self.readNWait()

        while 'd,STATUS,INIT' not in res:
            _log("Waiting for STATUS = INIT. Please enable the reader...", self.debug)
            res = self.readNWait()

        self.write2Serial("D,READER,1")  # enable reader
        while 'd,STATUS,IDLE' not in res:
            _log("Waiting for STATUS = IDLE...", self.debug)
            res = self.readNWait()

        _log("Slave device is IDLE and ready.", self.debug)

    # ------------------- vending helpers ------------------------------- #
    def detect_direct_vend(self, amount, product):
        response = self.writeNReadLn(f"D,REQ,{amount},{product}")
        if 'd,ERR,"-1"' in response:
            return False
        if 'd,STATUS,VEND' in response:
            return response
        return None

    def normal_vend(self, amount, product):
        _log("Please insert payment media...", self.debug)
        response = self.readNWait()
        if 'd,STATUS,CREDIT,' in response:
            credit = float(response.split(",")[-1])
            if credit >= float(amount):
                response = self.writeNReadLn(f"D,REQ,{amount},{product}")
                if 'd,STATUS,VEND' in response:
                    _log("Transaction success.", self.debug)
                    return True
        _log("Insufficient credit or failure.", self.debug)
        return False

    # -------------------- misc ----------------------------------------- #
    def cleanup(self):
        if self.ser:
            self.ser.close()
            _log("Serial port closed.", self.debug)

    def cancelTransaction(self):
        res = self.writeNReadLn("D,REQ,-1")
        _log(f"Transaction cancelled: {res}", self.debug)

    def endTransaction(self, amount, product, response):
        _log("Finalising transaction...", self.debug)
        if "SUCCESS" in response or "d,STATUS,RESULT,1" in response:
            _log(f"Transaction SUCCESS: {amount}€ for product {product}", self.debug)
            self.writeNReadLn("D,END")
        elif "FAILED" in response or "d,STATUS,RESULT,-1" in response:
            raise ValueError("Transaction denied by cashless device!")
        else:
            raise ValueError("Transaction failed!")
