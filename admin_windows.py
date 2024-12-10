# admin_windows.py
import tkinter as tk
from tkinter import messagebox, Toplevel, StringVar, TclError

# Pin Entry Window Class
class PinEntryWindow(Toplevel):
    def __init__(self, master, callback):
        super().__init__(master)
        self.callback = callback
        self.title("Enter PIN")
        self.geometry("300x400")
        self.configure(bg="#F0F0F0")

        self.timeout = 30000  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event
        self.reset_timeout()  # Initialize timeout tracking

        
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

        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_number(self, number):
        self.reset_timeout()  # Reset timeout on user interaction
        current_pin = self.entered_pin.get()
        self.entered_pin.set(current_pin + number)

    def on_clear(self):
        self.reset_timeout()  # Reset timeout on user interaction
        self.entered_pin.set("")

    def on_enter(self):
        pin = self.entered_pin.get()
        self.callback(pin)

        # Safely destroy without checking the master state
        try:
            self.destroy()
        except TclError as e:
            print(f"PinEntryWindow destroy error: {e}")


    def on_close(self):
        """Handle closing the window."""
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()


    def reset_timeout(self):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:  # Cancel any existing timeout event
            self.after_cancel(self.last_interaction)
        # Schedule the next timeout check
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle window closure on timeout."""
        #messagebox.showinfo("Session Expired", "Closing due to inactivity.")
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()


# Admin Options Window Class
class AdminOptionsWindow(Toplevel):
    def __init__(self, master, locker_id, unlock_callback, price_callback, locker_data, buttons, save_callback):
        super().__init__(master)
        self.locker_id = locker_id
        self.unlock_callback = unlock_callback
        self.price_callback = price_callback
        self.locker_data = locker_data
        self.buttons = buttons
        self.save_callback = save_callback


        self.title("Admin Options")
        self.geometry("300x200")
        self.configure(bg="#F0F0F0")


        self.timeout = 60000  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event
        self.reset_timeout()  # Initialize timeout tracking

        
        # Locker options label
        tk.Label(self, text=f"Locker {locker_id} Options", font=("Arial", 16)).pack(pady=10)

        # Unlock button
        unlock_button = tk.Button(self, text="Unlock Locker", font=("Arial", 14), command=self.on_unlock)
        unlock_button.pack(pady=5)

        # Change price button
        change_price_button = tk.Button(self, text="Change Price", font=("Arial", 14), command=self.on_change_price)
        change_price_button.pack(pady=5)

        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        

    def on_unlock(self):
        """Handle locker unlocking and mark it as available."""
        # Call the unlock callback to perform physical unlocking
        
        self.unlock_callback(self.locker_id)

        # Mark locker as available and reset button GUI
        self.locker_data[str(self.locker_id)]["status"] = True
        self.buttons[self.locker_id].config(bg="#C3C3C3", state="normal")  # Reset button
        self.save_callback(self.locker_data)

        # Close the admin options window
        self.destroy()

    def on_change_price(self):
        """Call the change price callback."""
        self.price_callback()
        self.destroy()


    def on_close(self):
        """Handle closing the window."""
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()

    def reset_timeout(self):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:  # Cancel any existing timeout event
            self.after_cancel(self.last_interaction)
        # Schedule the next timeout check
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle window closure on timeout."""
        #messagebox.showinfo("Session Expired", "Closing due to inactivity.")
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()


# Price Entry Window Class
class PriceEntryWindow(Toplevel):
    def __init__(self, master, locker_id, save_price_callback):
        super().__init__(master)
        self.title(f"Set Price for Locker {locker_id}")
        self.geometry("300x400")
        self.configure(bg="#F0F0F0")

        self.locker_id = locker_id
        self.save_price_callback = save_price_callback
        self.entered_price = StringVar()

        entry_display = tk.Entry(self, textvariable=self.entered_price, font=("Arial", 24), justify="center")
        entry_display.grid(row=0, column=0, columnspan=3, pady=10)

        self.timeout = 60000  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event
        self.reset_timeout()  # Initialize timeout tracking

        buttons = [
            ('1', 1, 0), ('2', 1, 1), ('3', 1, 2),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2),
            ('7', 3, 0), ('8', 3, 1), ('9', 3, 2),
            ('0', 4, 1), ('Enter', 4, 2), ('Clear', 4, 0)
        ]

        for (text, row, col) in buttons:
            if text == "Enter":
                # Call self.on_enter directly
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


        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)


    def on_number(self, number):
        self.reset_timeout()  # Reset timeout on user interaction
        current_price = self.entered_price.get()
        self.entered_price.set(current_price + number)

    def on_clear(self):
        self.reset_timeout()  # Reset timeout on user interaction
        self.entered_price.set("")

    def on_enter(self):
        """Save the entered price and call the callback."""
        try:
            # Validate the price input
            price = float(self.entered_price.get())

            # Call the callback with locker_id and the new price
            self.save_price_callback(self.locker_id, price)

            # Close the window after successfully saving the price
            self.destroy()
        except ValueError:
            # Show an error if the entered price is not a valid float
            messagebox.showerror("Invalid Input", "Please enter a valid price.")


    def on_close(self):
        """Handle closing the window."""
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()

    def reset_timeout(self):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:  # Cancel any existing timeout event
            self.after_cancel(self.last_interaction)
        # Schedule the next timeout check
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle window closure on timeout."""
        #messagebox.showinfo("Session Expired", "Closing due to inactivity.")
        if self.master and hasattr(self.master, '_exit_pin_window'):
            self.master._exit_pin_window = None  # Clear reference in the master app
        self.destroy()
