# main.py
import multiprocessing
from run_bot import main_bot
# Suppose you also have run_gui.py for your Tkinter code, if needed
from run_gui import main_gui

def main():
    bot_process = multiprocessing.Process(target=main_bot)
    bot_process.start()

    # Optionally, if you have a separate GUI:
    gui_process = multiprocessing.Process(target=main_gui)
    gui_process.start()

    bot_process.join()
    gui_process.join()

if __name__ == "__main__":
    main()
