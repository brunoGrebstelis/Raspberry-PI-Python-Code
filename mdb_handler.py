# ────────────────────────────────────────────────────────────────────────────────
# mdb_handler.py   – fully updated                                               #
# ────────────────────────────────────────────────────────────────────────────────
import serial
import io
import time
import threading
# mdb_handler.py – revised log setup  (≈ 12 lines)
import logging
from pathlib import Path
from datetime import datetime

LOG_DIR  = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "BLACK_BOX_POS.txt"

_logger = logging.getLogger("black_box_pos")   # a *dedicated* logger
_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, mode="a")
file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_logger.addHandler(file_handler)

_logger.propagate = False   # <── stops messages leaking to the root logger

def _log(msg: str, echo=False):
    """Write *msg* to the black-box and optionally to stdout."""
    _logger.info(msg)
    if echo:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {msg}")

# ───────────────────────────── serial-port mutex
_serial_lock = threading.Lock()          # protects all reads/writes

# ───────────────────────────── main class
class MDBHandler:
    VEND_TIMEOUT  = 20    # seconds to wait for RESULT in Direct Vend
    CREDIT_WINDOW = 15    # seconds to wait for card in Normal Vend

    def __init__(self, port="/dev/ttyACM0", debug=False):
        self.port  = port
        self.debug = debug
        self.ser   = None
        self.sio   = None
        _log(f"MDBHandler created for port {self.port}", self.debug)

    # ───────── serial initialisation
    def init_serial(self):
        """Open the serial port and wrapper."""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=1)
            self.sio = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser))
            time.sleep(1)                        # allow FTDI to settle
            _log("Serial port initialised.", self.debug)
        except Exception as e:
            _log(f"Serial initialisation error: {e}", True)
            raise
    initserial = init_serial                  # legacy alias

    # ───────── low-level I/O helpers
    def write2Serial(self, msg: str):
        with _serial_lock:
            self.sio.write(msg + "\n")
            self.sio.flush()

    def readNWait(self, tries: int = 5):
        """Read one line, retrying ~500 ms total."""
        with _serial_lock:
            for _ in range(tries):
                buf = self.sio.readline()
                if self.debug:
                    _log(f"Read: {buf.strip()}", True)
                if buf:
                    break
                time.sleep(0.1)
        return buf

    def writeNReadLn(self, msg: str):
        if self.debug:
            _log(f"Sending: {msg}", True)
        self.write2Serial(msg)
        return self.readNWait()

    # ───────── device initialisation
    def init_devices(self):
        """Put reader in Direct-Vend mode and enable it."""
        res = self.writeNReadLn("D,2")             # start Direct-Vend

        if 'D,ERR,"cashless master is on"' in res:
            _log("Restarting cashless device…", self.debug)
            self.write2Serial("D,0"); self.write2Serial("D,2")
            res = self.readNWait()

        # --- wait until we SEE INIT -----------------------------------------
        while "d,STATUS,INIT" not in res:
            _log("Waiting for STATUS = INIT…", self.debug)
            res = self.readNWait()

        # --- now enable the reader ------------------------------------------
        self.write2Serial("D,READER,1")

        # --- wait until the reader reports IDLE ------------------------------
        while "d,STATUS,IDLE" not in res:
            _log("Waiting for STATUS = IDLE…", self.debug)
            res = self.readNWait()

        _log("Slave device is IDLE and ready.", self.debug)

    # ───────── vend helpers
    def detect_direct_vend(self, amount, product):
        """Attempt Direct Vend; return True if STATUS,VEND seen."""
        rsp = self.writeNReadLn(f"D,REQ,{amount},{product}")
        if 'd,ERR,"-1"' in rsp:                 # reader refused
            return None
        if "d,STATUS,VEND" in rsp:
            return rsp
        return None

    def normal_vend(self, amount, product):
        """Wait for CREDIT then vend (timeout CREDIT_WINDOW s)."""
        _log("Please insert payment media…", self.debug)
        deadline = time.time() + self.CREDIT_WINDOW
        while time.time() < deadline:
            rsp = self.readNWait()
            if "d,STATUS,CREDIT," in rsp:
                credit = float(rsp.split(",")[-1])
                if credit >= float(amount):
                    rsp = self.writeNReadLn(f"D,REQ,{amount},{product}")
                    if "d,STATUS,VEND" in rsp:
                        _log("Transaction success.", self.debug)
                        return True
            time.sleep(0.2)
        _log("Insufficient credit or timeout.", self.debug)
        return False

    # ───────── transaction helpers
    def cancelTransaction(self):
        rsp = self.writeNReadLn("D,REQ,-1")
        _log(f"Transaction cancelled: {rsp}", self.debug)

    def endTransaction(self, amount, product, rsp):
        _log("Finalising transaction…", self.debug)
        if "d,STATUS,RESULT,1" in rsp or "SUCCESS" in rsp:
            _log(f"Transaction SUCCESS: {amount}€ for product {product}", self.debug)
            self.writeNReadLn("D,END")
        elif "d,STATUS,RESULT,-1" in rsp or "FAILED" in rsp:
            raise ValueError("Transaction denied by cashless device!")
        else:
            raise ValueError("Transaction failed!")

    # ───────── cleanup
    def end_comunication(self):
        """Disable reader & master, then close port."""
        self.write2Serial("D,READER,0"); self.write2Serial("D,0")
        self.cleanup()

    def cleanup(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            _log("Serial port closed.", self.debug)
