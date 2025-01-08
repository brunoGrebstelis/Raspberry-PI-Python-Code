# run_gui.py
from app import VendingMachineApp

def main_gui(bot_queue):
    app = VendingMachineApp(bot_queue)
    app.mainloop()
