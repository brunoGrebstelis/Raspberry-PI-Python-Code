# main.py
import multiprocessing
from run_bot import main_bot
from run_gui import main_gui

# --- program-start marker -----------------------------------------------
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
with (LOG_DIR / "PROGRAMM_RUNNED.txt").open("a", encoding="utf-8") as fp:
    fp.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}   PROGRAM START\n")
# -------------------------------------------------------------------------

def main():
    # Create a Queue for inter-process communication
    bot_queue = multiprocessing.Queue()

    # Bot process
    bot_proc = multiprocessing.Process(target=main_bot, args=(bot_queue,))
    bot_proc.start()

    # GUI (vending-machine) process
    gui_proc = multiprocessing.Process(target=main_gui, args=(bot_queue,))
    gui_proc.start()

    # Wait for them to exit
    bot_proc.join()
    gui_proc.join()

if __name__ == "__main__":
    main()
