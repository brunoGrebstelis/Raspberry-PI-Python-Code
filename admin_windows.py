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
    def __init__(self, master, locker_id, unlock_callback, price_callback, locker_data, buttons, save_callback, spi_handler, close_program_callback):
        super().__init__(master)
        self.locker_id = locker_id
        self.unlock_callback = unlock_callback
        self.price_callback = price_callback
        self.locker_data = locker_data
        self.buttons = buttons
        self.save_callback = save_callback
        self.spi_handler = spi_handler
        self.close_program_callback = close_program_callback

        self.title("Admin Options")
        self.geometry("300x300")
        self.configure(bg="#F0F0F0")

        self.timeout = 60000  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event
        self.reset_timeout()  # Initialize timeout tracking

        # Locker options label
        tk.Label(self, text=f"Locker {locker_id} Options", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="nsew")

        # Buttons
        buttons = [
            ("Unlock Locker", self.on_unlock),
            ("Change Price", self.on_change_price),
            ("Change Color", self.on_change_color),
            ("Change All Colors", self.on_change_all_color),
            ("Close Program", self.on_close_program)
        ]

        for row, (text, command) in enumerate(buttons, start=1):
            button = tk.Button(self, text=text, font=("Arial", 14), command=command)
            button.grid(row=row, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")

        # Configure grid for equal spacing
        for i in range(len(buttons) + 1):  # Number of buttons + label row
            self.grid_rowconfigure(i, weight=1)
        for j in range(2):  # Two columns
            self.grid_columnconfigure(j, weight=1)

        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_unlock(self):
        """Handle locker unlocking and mark it as available."""
        self.unlock_callback(self.locker_id)

        # Mark locker as available and reset button GUI
        self.locker_data[str(self.locker_id)]["status"] = True
        self.buttons[self.locker_id].config(bg="#C3C3C3", state="normal")  # Reset button
        self.save_callback(self.locker_data)

        self.destroy()

    def on_change_price(self):
        """Call the change price callback."""
        self.price_callback()
        self.destroy()

    def on_change_color(self):
        """Open the RGB Entry Window for a specific locker."""
        RGBEntryWindow(self.master, self.locker_id, self.spi_handler)
        self.destroy()
        

    def on_change_all_color(self):
        """Open the RGB Entry Window for all lockers."""
        RGBEntryWindow(self.master, 255, self.spi_handler)
        self.destroy()

    def on_close_program(self):
        """Run the close program callback to terminate the application."""
        self.close_program_callback()

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




class InformationWindow(tk.Toplevel):
    def __init__(self, master=None, timeout=60000):
        super().__init__(master)
        self.title("Information")
        self.geometry("800x460")  # Full screen for the given resolution
        self.configure(bg="#FFC0C0")  # Light red background to draw attention

        # Message content
        text_german = (
            "Leider ist das Schließfach blockiert.\n"
            "Für Rückerstattung oder Blumen kontaktieren Sie bitte:\n"
            "Janis: +4915757165517\n"
            "Aija: +4915782920110"
        )
        text_english = (
            "Unfortunately, the locker is jammed.\n"
            "To get a refund or flowers, please contact:\n"
            "Janis: +4915757165517\n"
            "Aija: +4915782920110"
        )

        # Labels for the German text (larger size, bold font)
        label_german = tk.Label(
            self, text=text_german, font=("Arial", 22, "bold"), bg="#FFC0C0", justify="center"
        )
        label_german.pack(pady=(40, 20))  # Add padding to create space between sections

        # Divider between languages
        separator = tk.Label(
            self, text="--------------------------", font=("Arial", 16), bg="#FFC0C0", justify="center"
        )
        separator.pack()

        # Labels for the English text
        label_english = tk.Label(
            self, text=text_english, font=("Arial", 18), bg="#FFC0C0", justify="center"
        )
        label_english.pack(pady=(20, 40))

        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Timeout to close the window
        self.after(timeout, self.on_close)

    def on_close(self):
        """Destroy the window."""
        self.destroy()

    @staticmethod
    def show(master=None):
        """Static method to show the window from another class."""
        window = InformationWindow(master)
        window.grab_set()  # Prevent interaction with other windows




class RGBEntryWindow(Toplevel):
    def __init__(self, master, locker_id, spi_handler):
        super().__init__(master)
        self.title("Enter RGB Values")
        self.geometry("400x400")  # Adjusted height and width
        self.configure(bg="#F0F0F0")

        self.locker_id = locker_id
        self.spi_handler = spi_handler

        self.timeout = 60000  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event
        self.reset_timeout()  # Initialize timeout tracking

        # StringVars to hold RGB values
        self.red_value = StringVar()
        self.green_value = StringVar()
        self.blue_value = StringVar()

        # Create input fields for RGB values
        tk.Label(self, text="Red(0-255):", font=("Arial", 14), bg="#F0F0F0").grid(row=0, column=0, columnspan=1, pady=5, padx=5, sticky="w")
        self.red_entry = tk.Entry(self, textvariable=self.red_value, font=("Arial", 14), justify="center")
        self.red_entry.grid(row=0, column=1, columnspan=2, pady=5, padx=5, sticky="nsew")

        tk.Label(self, text="Green(0-255):", font=("Arial", 14), bg="#F0F0F0").grid(row=1, column=0, columnspan=1, pady=5, padx=5, sticky="w")
        self.green_entry = tk.Entry(self, textvariable=self.green_value, font=("Arial", 14), justify="center")
        self.green_entry.grid(row=1, column=1, columnspan=2, pady=5, padx=5, sticky="nsew")

        tk.Label(self, text="Blue(0-255):", font=("Arial", 14), bg="#F0F0F0").grid(row=2, column=0, columnspan=1, pady=5, padx=5, sticky="w")
        self.blue_entry = tk.Entry(self, textvariable=self.blue_value, font=("Arial", 14), justify="center")
        self.blue_entry.grid(row=2, column=1, columnspan=2, pady=5, padx=5, sticky="nsew")

        # Numeric keypad and Save button
        self.create_keypad()

        # Handle the "X" button
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_keypad(self):
        buttons = [
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2),
            ('4', 4, 0), ('5', 4, 1), ('6', 4, 2),
            ('7', 5, 0), ('8', 5, 1), ('9', 5, 2),
            ('Clear', 6, 0), ('0', 6, 1), ('Save', 6, 2)
        ]

        for (text, row, col) in buttons:
            if text == "Clear":
                button = tk.Button(self, text=text, font=("Arial", 14), command=self.clear_inputs)
            elif text == "Save":
                button = tk.Button(self, text=text, font=("Arial", 14), command=self.save_rgb)
            else:
                button = tk.Button(self, text=text, font=("Arial", 14), command=lambda t=text: self.on_number(t))
            button.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        # Set equal weights for all rows and columns
        for i in range(7):  # Adjust for rows 0-6
            self.grid_rowconfigure(i, weight=1)
        for j in range(3):  # 3 columns
            self.grid_columnconfigure(j, weight=1, uniform="column")

    def on_number(self, number):
        self.reset_timeout()  # Reset timeout on user interaction
        if self.focus_get() == self.red_entry:
            current = self.red_value.get()
            self.red_value.set(current + number)
        elif self.focus_get() == self.green_entry:
            current = self.green_value.get()
            self.green_value.set(current + number)
        elif self.focus_get() == self.blue_entry:
            current = self.blue_value.get()
            self.blue_value.set(current + number)

    def clear_inputs(self):
        self.reset_timeout()  # Reset timeout on user interaction
        self.red_value.set("")
        self.green_value.set("")
        self.blue_value.set("")

    def save_rgb(self):
        try:
            red = int(self.red_value.get())
            green = int(self.green_value.get())
            blue = int(self.blue_value.get())

            if not (0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255):
                raise ValueError("RGB values must be between 0 and 255.")

            import json

            # Load existing lockers.json file
            with open("lockers.json", "r") as file:
                lockers = json.load(file)

            # Update lockers with the new RGB values
            if self.locker_id == 255:  # Update all lockers
                for locker in lockers.values():
                    locker["red"] = red
                    locker["green"] = green
                    locker["blue"] = blue
                self.spi_handler.set_led_color(255, red, green, blue)
            else:  # Update a specific locker
                locker = lockers[str(self.locker_id)]
                locker["red"] = red
                locker["green"] = green
                locker["blue"] = blue
                self.spi_handler.set_led_color(self.locker_id, red, green, blue)

            # Save the updated lockers.json file
            with open("lockers.json", "w") as file:
                json.dump(lockers, file, indent=4)

            messagebox.showinfo("Success", "RGB values saved successfully.")
            self.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def on_close(self):
        self.destroy()

    def reset_timeout(self):
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        self.destroy()

# Example of how to show this window (integration with a main application):
# root = tk.Tk()
# spi_handler = SPIHandler()
# rgb_window = RGBEntryWindow(root, 255, spi_handler)
# root.mainloop()

