# app.py
import tkinter as tk
from tkinter import messagebox
import time
import os
from admin_windows import PinEntryWindow, AdminOptionsWindow, PriceEntryWindow
from utils import load_locker_data, save_locker_data, send_command, log_event
from spi_handler import SPIHandler
from scheduler import Scheduler

class VendingMachineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vending Machine")
        self.geometry("800x480")
        self.configure(bg="#C3C3C3")
        self.selected_locker = None
        self.locker_data = load_locker_data()

        # Initialize the scheduler
        self.scheduler = Scheduler()
        self.scheduler.start()

        # Load images (assuming they're in an 'img' folder)
        self.pay_image = tk.PhotoImage(file=os.path.join("img", "icon3.png"))

        # Load button images
        self.button_images = [tk.PhotoImage(file=os.path.join("img", f"button{i}.png")) for i in range(1, 13)]

        
        # SPIHandler initialization with error handling
        try:
            self.spi_handler = SPIHandler(bus=0, device=0, speed_hz=500000)
            self.spi_enabled = True
            print("SPI initialized successfully.")
            self.transfer_prices_to_stm32()
        except (ImportError, FileNotFoundError, AttributeError) as e:
            self.spi_handler = None
            self.spi_enabled = False
            print(f"SPI not available on this system: {e}")

        self.protocol("WM_DELETE_WINDOW", self.on_close)  # Ensure SPI is closed on exit


        # Setup buttons
        self.create_locker_buttons()

        # Create PAY button
        self.pay_button = tk.Button(self, image=self.pay_image, command=self.process_payment, borderwidth=0, bg="#C3C3C3", activebackground="#C3C3C3", highlightthickness=0)
        self.pay_button.place(x=140, y=385, width=520, height=70)

        # Keyboard listener for Escape key
        self.bind("<Key>", self.keyboard_listener)

    def create_locker_buttons(self):
        button_specs = [
            {"size": (170, 170), "pos": (135, 20)},
            {"size": (80, 80), "pos": (315, 20)},
            {"size": (80, 80), "pos": (405, 20)},
            {"size": (80, 80), "pos": (495, 20)},
            {"size": (80, 80), "pos": (585, 20)},
            {"size": (80, 80), "pos": (315, 110)},
            {"size": (80, 80), "pos": (405, 110)},
            {"size": (80, 80), "pos": (495, 110)},
            {"size": (80, 80), "pos": (585, 110)},
            {"size": (170, 170), "pos": (135, 200)},
            {"size": (170, 170), "pos": (315, 200)},
            {"size": (170, 170), "pos": (495, 200)}
        ]

        self.buttons = {}
        for i, spec in enumerate(button_specs, start=1):
            locker_id = str(i)
            status = self.locker_data[locker_id]["status"]
            button = tk.Button(self, image=self.button_images[i-1], text=str(i), font=("Arial", 18, "bold"), bg="#C3C3C3", activebackground="#C3C3C3", state="disabled" if not status else "normal", borderwidth=0, fg="black", highlightthickness=0, command=lambda i=i: self.select_locker(i))
            button.place(x=spec["pos"][0], y=spec["pos"][1], width=spec["size"][0], height=spec["size"][1])
            button.bind("<ButtonPress-1>", self.on_button_press)
            button.bind("<ButtonRelease-1>", self.on_button_release)
            self.buttons[i] = button

    def select_locker(self, locker_id):
        if self.selected_locker is not None:
            self.buttons[self.selected_locker].config(bg="#C3C3C3", activebackground="#C3C3C3")
        self.selected_locker = locker_id
        self.buttons[locker_id].config(bg="green", activebackground="green")

    def process_payment(self):
        if self.selected_locker is None:
            messagebox.showwarning("No Selection", "Please select a locker before paying.")
            return
        payment_successful = True  # Replace with actual payment handling
        if payment_successful:
            locker_id = self.selected_locker
            price = self.locker_data[str(locker_id)]["price"]
            self.locker_data[str(locker_id)]["status"] = False
            self.buttons[locker_id].config(state="disabled")
            save_locker_data(self.locker_data)
            log_event(locker_id, price)
            self.unlock_locker(locker_id)
            self.selected_locker = None
            self.buttons[locker_id].config(bg="#C3C3C3", activebackground="#C3C3C3")


    def unlock_locker(self, locker_id):
        send_command(f"UNLOCK:{locker_id}")
        messagebox.showinfo("Locker Unlocked", f"Locker {locker_id} has been unlocked.")
        if self.spi_enabled:
            self.spi_handler.set_led_color(locker_id, 255, 0, 0)  # Example SPI command
        else:
            print("SPI is disabled, skipping SPI commands.")

    def on_button_press(self, event):
        self.press_time = time.time()

    def on_button_release(self, event):
        hold_duration = time.time() - self.press_time
        if hold_duration >= 2:
            locker_id = int(event.widget["text"])
            self.prompt_admin_options(locker_id)

    def prompt_admin_options(self, locker_id):
        def pin_callback(pin):
            if pin == "4671":
                self.show_admin_options(locker_id)
            else:
                messagebox.showerror("Incorrect PIN", "The PIN entered is incorrect.")

        PinEntryWindow(self, pin_callback)

    def show_admin_options(self, locker_id):
        """Show admin options for a specific locker."""
        AdminOptionsWindow(
            self,
            locker_id=locker_id,
            unlock_callback=self.unlock_locker_callback,
            price_callback=self.change_price_callback,
            locker_data=self.locker_data,
            buttons=self.buttons,
            save_callback=save_locker_data  # Pass the save function as a callback
        )



    def unlock_locker_callback(self, locker_id):
        """Handle locker unlocking and reset its availability."""
        send_command(f"UNLOCK:{locker_id}")  # Send unlock command to STM32
        messagebox.showinfo("Locker Unlocked", f"Locker {locker_id} has been unlocked.")



    def change_price_callback(self):
        """Callback for changing the price of a selected locker."""
        locker_id = self.selected_locker
        if locker_id is not None:
            # Open the price entry window
            PriceEntryWindow(self, locker_id, self.save_price_and_update_spi)
        else:
            messagebox.showwarning("No Locker Selected", "Please select a locker to change its price.")



    def save_price_and_update_spi(self, locker_id, new_price):
        """
        Save the new price for a locker and update STM32 via SPI.
        :param locker_id: Locker number to update.
        :param new_price: New price in euros.
        """
        # Save the price to locker_data
        self.locker_data[str(locker_id)]["price"] = new_price
        save_locker_data(self.locker_data)

        # Send the new price to STM32
        if self.spi_enabled:
            self.spi_handler.set_price(locker_number=locker_id, price=new_price)
        else:
            print("SPI is disabled, skipping SPI commands.")

        messagebox.showinfo("Price Updated", f"Price for Locker {locker_id} set to {new_price:.2f}€")



    def transfer_prices_to_stm32(self):
        """
        Transfer price information from JSON to STM32 via SPI.
        """
        if self.spi_enabled:
            for locker_id, data in self.locker_data.items():
                price = data["price"]
                locker_number = int(locker_id)
                self.spi_handler.set_price(locker_number, price)
                print(f"Price for Locker {locker_number} set to {price:.2f}€")
                time.sleep(0.05)
        else:
            print("SPI is disabled, skipping price transfer.")
            


    def keyboard_listener(self, event):
        if event.keysym == 'Escape':
            self.quit()

    def on_close(self):
        """Handle application exit."""
        if self.scheduler:
            self.scheduler.stop()
            print("Scheduler stopped.")

        if hasattr(self, 'spi_handler') and self.spi_handler:
            try:
                self.spi_handler.close()
            except Exception as e:
                print(f"Error during SPIHandler cleanup: {e}")
                
        self.destroy()

