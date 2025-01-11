# admin_frames.py
import tkinter as tk
from tkinter import messagebox
import json

class AdminOptionsFrame(tk.Frame):
    def __init__(self, master, locker_id, unlock_callback, price_callback, locker_data, buttons, save_callback, spi_handler, close_program_callback, timeout=60000):
        """
        Initialize the AdminOptionsFrame.

        :param master: Parent widget.
        :param locker_id: ID of the locker.
        :param unlock_callback: Function to unlock the locker.
        :param price_callback: Function to change the price.
        :param locker_data: Data of lockers.
        :param buttons: Locker buttons.
        :param save_callback: Function to save locker data.
        :param spi_handler: SPI handler object.
        :param close_program_callback: Function to close the program.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.locker_id = locker_id
        self.unlock_callback = unlock_callback
        self.price_callback = price_callback
        self.locker_data = locker_data
        self.buttons = buttons
        self.save_callback = save_callback
        self.spi_handler = spi_handler
        self.close_program_callback = close_program_callback
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid layout
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        self.grid_rowconfigure(1, weight=1)  # For the label
        for i in range(2, 7):
            self.grid_rowconfigure(i, weight=1)
        for i in range(2):
            self.grid_columnconfigure(i, weight=1)

        # Create "X" button to close the frame
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"), bd=0,
            bg="#F0F0F0", activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=1, sticky="ne", padx=20, pady=20)
        self.close_button.config(width=4, height=2)

        # Locker options label
        label = tk.Label(
            self, text=f"Locker {locker_id} Options", font=("Arial", 36, "bold"), bg="#F0F0F0"
        )
        label.grid(row=1, column=0, columnspan=2, pady=20, padx=10, sticky="nsew")

        # Buttons
        buttons = [
            ("Unlock Locker", self.on_unlock),
            ("Change Price", self.on_change_price),
            ("Change Color", self.on_change_color),
            ("Change All Colors", self.on_change_all_color),
            ("Close Program", self.on_close_program)
        ]

        for idx, (text, command) in enumerate(buttons, start=2):
            button = tk.Button(
                self, text=text, font=("Arial", 27), command=command
            )
            button.grid(row=idx, column=0, columnspan=2, padx=30, pady=15, sticky="nsew")
            button.config(width=15, height=3)

        # Bind interactions within the frame to reset the timeout
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_unlock(self):
        """Handle locker unlocking and mark it as available."""
        self.reset_timeout()
        self.unlock_callback(self.locker_id)

        # Mark locker as available and reset button GUI
        self.locker_data[str(self.locker_id)]["status"] = True
        self.buttons[self.locker_id].config(bg="#C3C3C3", state="normal")  # Reset button
        self.save_callback(self.locker_data)

        self.hide()

    def on_change_price(self):
        """Call the change price callback."""
        self.reset_timeout()
        self.price_callback()
        self.hide()

    def on_change_color(self):
        """Open the RGB Entry Frame for a specific locker."""
        self.reset_timeout()
        self.master.rgb_entry_frame.show(self.locker_id)
        self.hide()

    def on_change_all_color(self):
        """Open the RGB Entry Frame for all lockers."""
        self.reset_timeout()
        self.master.rgb_entry_frame.show_all()
        self.hide()

    def on_close_program(self):
        """Run the close program callback to terminate the application."""
        self.reset_timeout()
        self.close_program_callback()

    def on_close(self):
        """Handle closing the frame via the "X" button."""
        self.hide()

    def show(self):
        """Display the AdminOptionsFrame."""
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def hide(self):
        """Hide the AdminOptionsFrame."""
        self.place_forget()
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle frame closure on timeout."""
        self.hide()


class PriceEntryFrame(tk.Frame):
    def __init__(self, master, locker_id, save_price_callback, timeout=60000):
        """
        Initialize the PriceEntryFrame.

        :param master: Parent widget.
        :param locker_id: ID of the locker.
        :param save_price_callback: Function to save the entered price.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.locker_id = locker_id
        self.save_price_callback = save_price_callback
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        self.grid_rowconfigure(1, weight=1)  # For the Title label
        self.grid_rowconfigure(2, weight=1)  # For the Entry widget
        for i in range(3, 8):
            self.grid_rowconfigure(i, weight=1)
        for i in range(3):
            self.grid_columnconfigure(i, weight=1)

        # "X" button
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"),
            bd=0, bg="#F0F0F0", activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=2, sticky="ne", padx=20, pady=20)
        self.close_button.config(width=4, height=2)

        # Title label
        self.title_label = tk.Label(
            self, text=f"Set Price for Locker {locker_id}", font=("Arial", 36, "bold"), bg="#F0F0F0"
        )
        self.title_label.grid(row=1, column=0, columnspan=3, pady=20)

        # Entry widget
        self.entered_price = tk.StringVar()
        self.entry_display = tk.Entry(
            self, textvariable=self.entered_price, font=("Arial", 54),
            justify="center"
        )
        self.entry_display.grid(row=2, column=0, columnspan=3, pady=45, padx=75, sticky="nsew")

        # PIN buttons
        buttons = [
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2),
            ('4', 4, 0), ('5', 4, 1), ('6', 4, 2),
            ('7', 5, 0), ('8', 5, 1), ('9', 5, 2),
            ('0', 6, 1), ('Enter', 6, 2), ('Clear', 6, 0)
        ]

        for (text, row, col) in buttons:
            if text == "Enter":
                button = tk.Button(self, text=text, font=("Arial", 27), command=self.on_enter)
            elif text == "Clear":
                button = tk.Button(self, text=text, font=("Arial", 27), command=self.on_clear)
            else:
                button = tk.Button(
                    self, text=text, font=("Arial", 27),
                    command=lambda t=text: self.on_number(t)
                )
            button.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
            button.config(width=7, height=3)

        # Bind interactions to reset timeout
        self.entry_display.bind("<Key>", self.reset_timeout)
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_number(self, number):
        """Handle number button presses."""
        self.reset_timeout()
        current_price = self.entered_price.get()
        self.entered_price.set(current_price + number)

    def on_clear(self):
        """Clear the entered price."""
        self.reset_timeout()
        self.entered_price.set("")

    def on_enter(self):
        """Save the entered price and execute the callback."""
        self.reset_timeout()
        try:
            price = float(self.entered_price.get())
            self.save_price_callback(self.locker_id, price)
            self.hide()
        except ValueError:
            print("Invalid Input", "Please enter a valid price.")

    def on_close(self):
        """Handle closing the frame via the "X" button."""
        self.hide()

    def show(self, locker_id):
        """Display the PriceEntryFrame."""
        self.locker_id = locker_id
        self.title_label.config(text=f"Set Price for Locker {locker_id}")
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def hide(self):
        """Hide the PriceEntryFrame."""
        self.place_forget()
        self.entered_price.set("")
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle frame closure on timeout."""
        self.hide()


class InformationFrame(tk.Frame):
    def __init__(self, master=None, timeout=60000):
        """
        Initialize the InformationFrame.

        :param master: Parent widget.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#FFC0C0")
        self.master = master
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # "X" button
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"),
            bd=0, bg="#FFC0C0", activebackground="#FFC0C0"
        )
        self.close_button.place(relx=0.95, rely=0.05, anchor="ne")

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
            self, text=text_german, font=("Arial", 33, "bold"), bg="#FFC0C0", justify="center"
        )
        label_german.pack(pady=(60, 30))

        # Divider between languages
        separator = tk.Label(
            self, text="--------------------------", font=("Arial", 24), bg="#FFC0C0", justify="center"
        )
        separator.pack()

        # Labels for the English text
        label_english = tk.Label(
            self, text=text_english, font=("Arial", 27), bg="#FFC0C0", justify="center"
        )
        label_english.pack(pady=(30, 60))

        # Bind interactions to reset timeout
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_close(self):
        """Destroy the frame."""
        self.hide()

    def show(self):
        """Display the InformationFrame."""
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def hide(self):
        """Hide the InformationFrame."""
        self.place_forget()
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle frame closure on timeout."""
        self.hide()


class RGBEntryFrame(tk.Frame):
    def __init__(self, master, locker_id, spi_handler, timeout=60000):
        """
        Initialize the RGBEntryFrame.

        :param master: Parent widget.
        :param locker_id: ID of the locker.
        :param spi_handler: SPI handler object.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.locker_id = locker_id
        self.spi_handler = spi_handler
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        for i in range(1, 8):
            self.grid_rowconfigure(i, weight=1)
        for j in range(3):
            self.grid_columnconfigure(j, weight=1)

        # "X" button
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"),
            bd=0, bg="#F0F0F0", activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=2, sticky="ne", padx=20, pady=20)
        self.close_button.config(width=4, height=2)

        # StringVars to hold RGB values
        self.red_value = tk.StringVar()
        self.green_value = tk.StringVar()
        self.blue_value = tk.StringVar()

        # Create input fields for RGB values
        tk.Label(
            self, text="Red(0-255):", font=("Arial", 21), bg="#F0F0F0"
        ).grid(row=1, column=0, pady=15, padx=15, sticky="w")
        self.red_entry = tk.Entry(
            self, textvariable=self.red_value, font=("Arial", 27), justify="center"
        )
        self.red_entry.grid(row=1, column=1, columnspan=2, pady=15, padx=15, sticky="nsew")

        tk.Label(
            self, text="Green(0-255):", font=("Arial", 21), bg="#F0F0F0"
        ).grid(row=2, column=0, pady=15, padx=15, sticky="w")
        self.green_entry = tk.Entry(
            self, textvariable=self.green_value, font=("Arial", 27), justify="center"
        )
        self.green_entry.grid(row=2, column=1, columnspan=2, pady=15, padx=15, sticky="nsew")

        tk.Label(
            self, text="Blue(0-255):", font=("Arial", 21), bg="#F0F0F0"
        ).grid(row=3, column=0, pady=15, padx=15, sticky="w")
        self.blue_entry = tk.Entry(
            self, textvariable=self.blue_value, font=("Arial", 27), justify="center"
        )
        self.blue_entry.grid(row=3, column=1, columnspan=2, pady=15, padx=15, sticky="nsew")

        # Numeric keypad and Save button
        self.create_keypad()

        # Bind interactions to reset timeout
        for child in self.winfo_children():
            if isinstance(child, tk.Button) or isinstance(child, tk.Entry):
                child.bind("<Button-1>", self.reset_timeout)
                child.bind("<Key>", self.reset_timeout)

        self.reset_timeout()

    def create_keypad(self):
        buttons = [
            ('1', 4, 0), ('2', 4, 1), ('3', 4, 2),
            ('4', 5, 0), ('5', 5, 1), ('6', 5, 2),
            ('7', 6, 0), ('8', 6, 1), ('9', 6, 2),
            ('Clear', 7, 0), ('0', 7, 1), ('Save', 7, 2)
        ]

        for (text, row, col) in buttons:
            if text == "Clear":
                button = tk.Button(
                    self, text=text, font=("Arial", 21), command=self.clear_inputs
                )
            elif text == "Save":
                button = tk.Button(
                    self, text=text, font=("Arial", 21), command=self.save_rgb
                )
            else:
                button = tk.Button(
                    self, text=text, font=("Arial", 21),
                    command=lambda t=text: self.on_number(t)
                )
            button.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
            button.config(width=7, height=3)

    def on_number(self, number):
        """Handle number button presses."""
        self.reset_timeout()
        focused = self.focus_get()
        if focused == self.red_entry:
            current = self.red_value.get()
            self.red_value.set(current + number)
        elif focused == self.green_entry:
            current = self.green_value.get()
            self.green_value.set(current + number)
        elif focused == self.blue_entry:
            current = self.blue_value.get()
            self.blue_value.set(current + number)

    def clear_inputs(self):
        """Clear all RGB input fields."""
        self.reset_timeout()
        self.red_value.set("")
        self.green_value.set("")
        self.blue_value.set("")

    def save_rgb(self):
        """Save the entered RGB values."""
        self.reset_timeout()
        try:
            red = int(self.red_value.get())
            green = int(self.green_value.get())
            blue = int(self.blue_value.get())

            if not (0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255):
                raise ValueError("RGB values must be between 0 and 255.")

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

            print("Success", "RGB values saved successfully.")
            self.hide()

        except ValueError as e:
            print("Invalid Input", str(e))
        except Exception as e:
            print("Error", f"An error occurred: {str(e)}")

    def on_close(self):
        """Handle closing the frame via the "X" button."""
        self.hide()

    def show(self, locker_id):
        """Display the RGBEntryFrame for a specific locker or all lockers."""
        self.locker_id = locker_id
        if locker_id == 255:
            title = "Set RGB for All Lockers"
        else:
            title = f"Set RGB for Locker {locker_id}"
        # Optionally update a title label if you have one
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def show_all(self):
        """Display the RGBEntryFrame for all lockers."""
        self.show(255)

    def hide(self):
        """Hide the RGBEntryFrame."""
        self.place_forget()
        self.red_value.set("")
        self.green_value.set("")
        self.blue_value.set("")
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle frame closure on timeout."""
        self.hide()


class PaymentPopupFrame(tk.Frame):
    def __init__(self, master, cancel_callback, timeout=30000):
        """
        Initialize the PaymentPopupFrame.

        :param master: Parent widget.
        :param cancel_callback: Function to cancel the payment.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#00AA00")  # Changed to a more visible color
        self.master = master
        self.cancel_callback = cancel_callback
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid to layout widgets properly
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        self.grid_rowconfigure(1, weight=1)  # For the main message
        self.grid_rowconfigure(2, weight=0)  # For the "Cancel" button
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # "X" button to close the frame
        self.close_button = tk.Button(
            self, text="X", command=self.on_cancel, font=("Arial", 24, "bold"),
            bd=0, bg="#00AA00", activebackground="#008800", fg="white"
        )
        self.close_button.grid(row=0, column=1, sticky="ne", padx=10, pady=10)

        # Main message label
        self.message_label = tk.Label(
            self,
            text="Follow the instructions on the terminal.",
            font=("Arial", 24, "bold"),
            bg="#00AA00",
            fg="white",
            wraplength=400,
            justify="center"
        )
        self.message_label.grid(row=1, column=0, columnspan=2, padx=20, pady=40)

        # "Cancel" button
        self.cancel_button = tk.Button(
            self, text="Cancel", command=self.on_cancel, font=("Arial", 24),
            bg="#FF3333", fg="white", activebackground="#CC0000", activeforeground="white"
        )
        self.cancel_button.grid(row=2, column=0, columnspan=2, pady=20)

        # Bind interactions to reset timeout
        for child in self.winfo_children():
            if isinstance(child, tk.Button) or isinstance(child, tk.Label):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_cancel(self):
        """Handle cancellation via the 'X' or 'Cancel' button."""
        print("PaymentPopupFrame: Cancel button clicked.")  # Debugging
        self.cancel_callback()
        self.hide()

    def show(self):
        """Display the PaymentPopupFrame."""
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()
        print("PaymentPopupFrame: Frame shown.")  # Debugging

    def hide(self):
        """Hide the PaymentPopupFrame."""
        self.place_forget()
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None
        print("PaymentPopupFrame: Frame hidden.")  # Debugging

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)
        print("PaymentPopupFrame: Timeout reset.")  # Debugging

    def on_timeout(self):
        """Handle frame closure on timeout."""
        print("PaymentPopupFrame: Timeout reached. Hiding frame.")  # Debugging
        self.hide()


class PinEntryFrame(tk.Frame):
    def __init__(self, master, callback, timeout=30000):
        """
        Initialize the PinEntryFrame.

        :param master: Parent widget.
        :param callback: Function to call with the entered PIN.
        :param timeout: Timeout duration in milliseconds (default is 30,000 ms).
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.callback = callback
        self.timeout = timeout  # Timeout duration in milliseconds
        self.last_interaction = None  # Placeholder for the timeout event

        # Configure grid layout for responsive design
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        self.grid_rowconfigure(1, weight=1)  # For the Entry widget
        for i in range(2, 7):
            self.grid_rowconfigure(i, weight=1)
        for i in range(3):
            self.grid_columnconfigure(i, weight=1)

        # Create "X" button to close the frame
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"),
            bd=0, bg="#F0F0F0", activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=2, sticky="ne", padx=20, pady=20)
        self.close_button.config(width=4, height=2)

        # Create Entry widget for PIN
        self.entered_pin = tk.StringVar()
        self.entry_display = tk.Entry(
            self, textvariable=self.entered_pin, font=("Arial", 54),
            justify="center", show="*"
        )
        self.entry_display.grid(row=1, column=0, columnspan=3, pady=60, padx=90)

        # Create PIN buttons
        buttons = [
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('4', 3, 0), ('5', 3, 1), ('6', 3, 2),
            ('7', 4, 0), ('8', 4, 1), ('9', 4, 2),
            ('0', 5, 1), ('Enter', 5, 2), ('Clear', 5, 0)
        ]

        for (text, row, col) in buttons:
            if text == "Enter":
                button = tk.Button(self, text=text, font=("Arial", 27), command=self.on_enter)
            elif text == "Clear":
                button = tk.Button(self, text=text, font=("Arial", 27), command=self.on_clear)
            else:
                button = tk.Button(
                    self, text=text, font=("Arial", 27),
                    command=lambda t=text: self.on_number(t)
                )
            button.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
            button.config(width=7, height=3)

        # Bind interactions within the frame to reset the timeout
        self.entry_display.bind("<Key>", self.reset_timeout)
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_number(self, number):
        """Handle number button presses in PIN entry."""
        self.reset_timeout()
        current_pin = self.entered_pin.get()
        self.entered_pin.set(current_pin + number)

    def on_clear(self):
        """Clear the entered PIN."""
        self.reset_timeout()
        self.entered_pin.set("")

    def on_enter(self):
        """Validate the entered PIN and execute the callback."""
        self.reset_timeout()
        pin = self.entered_pin.get()
        self.callback(pin)
        self.hide()

    def on_close(self):
        """Handle closing the frame via the "X" button."""
        self.hide()

    def show(self):
        """Display the PinEntryFrame."""
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()  # Bring the frame to the front
        self.focus_set()  # Set focus to the frame
        self.reset_timeout()  # Initialize/reset the timeout timer

    def hide(self):
        """Hide the PinEntryFrame."""
        self.place_forget()
        self.entered_pin.set("")  # Clear the entered PIN
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Handle frame closure on timeout."""
        self.hide()
