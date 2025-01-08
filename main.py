# main.py
import multiprocessing
from run_bot import main_bot
from run_gui import main_gui

def main():
    # Create a Queue for inter-process communication
    bot_queue = multiprocessing.Queue()

    # Bot process
    bot_proc = multiprocessing.Process(target=main_bot, args=(bot_queue,))
    bot_proc.start()

    # GUI (vending machine) process
    gui_proc = multiprocessing.Process(target=main_gui, args=(bot_queue,))
    gui_proc.start()

    # Wait for them to exit
    bot_proc.join()
    gui_proc.join()

if __name__ == "__main__":
    main()
