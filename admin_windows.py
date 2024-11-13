# admin_windows.py
import tkinter as tk
from tkinter import messagebox, Toplevel, StringVar

# Pin Entry Window Class
class PinEntryWindow(Toplevel):
    def __init__(self, master, callback):
        super().__init__(master)
        self.callback = callback
        self.title("Enter PIN")
        self.geometry("300x400")
        self.configure(bg="#F0F0F0")
        
        self.entered_pin = StringVar()
        entry_display = tk.Entry(self, textvariable=self.entered_pin, font=("Arial", 24), justify="center", show="*")
        entry_display.grid(row=0, column=0, columnspan=3, pady=10)

        buttons = [
            ('1', 1, 0), ('2', 1, 1), ('3', 1, 2),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2),
            ('7', 3, 0), ('8', 3, 1), ('9', 3, 2),
            ('0', 4, 1), ('Enter', 4, 2), ('Clear', 4, 0)
        ]
        
        for (text, row, col) in buttons:
            if text == "Enter":
                button = tk.Button(self, text=text, font=("Arial", 18), command=self.on_enter)
            elif text == "Clear":
                button = tk.Button(self, text=text, font=("Arial", 18), command=self.on_clear)
            else:
                button = tk.Button(self, text=text, font=("Arial", 18), command=lambda t=text: self.on_number(t))
            button.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            button.config(width=5, height=2)

        for i in range(5):
            self.grid_rowconfigure(i, weight=1)
            self.grid_columnconfigure(i % 3, weight=1)

    def on_number(self, number):
        current_pin = self.entered_pin.get()
        self.entered_pin.set(current_pin + number)

    def on_clear(self):
        self.entered_pin.set("")

    def on_enter(self):
        pin = self.entered_pin.get()
        self.callback(pin)
        self.destroy()


# Admin Options Window Class
class AdminOptionsWindow(Toplevel):
    def __init__(self, master, locker_id, unlock_callback, price_callback):
        super().__init__(master)
        self.title("Admin Options")
        self.geometry("300x200")
        self.configure(bg="#F0F0F0")
        
        tk.Label(self, text=f"Locker {locker_id} Options", font=("Arial", 16)).pack(pady=10)

        unlock_button = tk.Button(self, text="Unlock Locker", font=("Arial", 14), command=lambda: self.on_unlock(unlock_callback))
        unlock_button.pack(pady=5)

        change_price_button = tk.Button(self, text="Change Price", font=("Arial", 14), command=lambda: self.on_change_price(price_callback))
        change_price_button.pack(pady=5)

    def on_unlock(self, unlock_callback):
        unlock_callback()
        self.destroy()

    def on_change_price(self, price_callback):
        price_callback()
        self.destroy()

# Price Entry Window Class
class PriceEntryWindow(Toplevel):
    def __init__(self, master, locker_id, save_price_callback):
        super().__init__(master)
        self.title(f"Set Price for Locker {locker_id}")
        self.geometry("300x400")
        self.configure(bg="#F0F0F0")
        
        self.entered_price = StringVar()
        entry_display = tk.Entry(self, textvariable=self.entered_price, font=("Arial", 24), justify="center")
        entry_display.grid(row=0, column=0, columnspan=3, pady=10)

        buttons = [
            ('1', 1, 0), ('2', 1, 1), ('3', 1, 2),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2),
            ('7', 3, 0), ('8', 3, 1), ('9', 3, 2),
            ('0', 4, 1), ('Enter', 4, 2), ('Clear', 4, 0)
        ]

        for (text, row, col) in buttons:
            if text == "Enter":
                button = tk.Button(self, text=text, font=("Arial", 18), command=lambda: self.on_enter(save_price_callback))
            elif text == "Clear":
                button = tk.Button(self, text=text, font=("Arial", 18), command=self.on_clear)
            else:
                button = tk.Button(self, text=text, font=("Arial", 18), command=lambda t=text: self.on_number(t))
            button.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            button.config(width=5, height=2)

        for i in range(5):
            self.grid_rowconfigure(i, weight=1)
            self.grid_columnconfigure(i % 3, weight=1)

    def on_number(self, number):
        current_price = self.entered_price.get()
        self.entered_price.set(current_price + number)

    def on_clear(self):
        self.entered_price.set("")

    def on_enter(self, save_price_callback):
        try:
            price = float(self.entered_price.get())
            save_price_callback(price)
            self.destroy()
        except ValueError:
            messagebox.showerror("Invalid Price", "Please enter a valid price.")
