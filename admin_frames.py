# admin_frames.py
import tkinter as tk
from tkinter import messagebox
import json
from gui import BG_COLOR, GREEN_COLOR, TAG_COLOR
import sys
import time
import os

class AdminOptionsFrame(tk.Frame):
    def __init__(
            self, 
            master, 
            locker_id, 
            unlock_callback, 
            price_callback, 
            locker_data, 
            buttons, 
            save_callback, 
            spi_handler, 
            close_program_callback, 
            lock_order_callback,   
            cancel_order_callback,
            timeout=60000
    ):
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
        :param lock_order_callback: Function to lock the order (NEW).
        :param cancel_order_callback: Function to cancel any ongoing order on show.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#F0F0F0")
        self.config(width=1200, height=1100)
        self.master = master
        self.locker_id = locker_id
        self.unlock_callback = unlock_callback
        self.price_callback = price_callback
        self.locker_data = locker_data
        self.buttons = buttons
        self.save_callback = save_callback
        self.spi_handler = spi_handler
        self.close_program_callback = close_program_callback
        self.lock_order_callback = lock_order_callback
        self.cancel_order_callback = cancel_order_callback
        self.timeout = timeout
        self.last_interaction = None

        self.pack_propagate(False)  # or self.grid_propagate(False) if using grid
        self.grid_propagate(False)

        # Configure grid layout
        self.grid_rowconfigure(0, weight=0)  # For the "X" button
        self.grid_rowconfigure(1, weight=1)  # For the label
        for i in range(2, 10):  # We’ll have more rows now
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
        self.label = tk.Label(
            self, text=f"Locker {self.locker_id} Options", font=("Arial", 36, "bold"), bg="#F0F0F0"
        )
        self.label.grid(row=1, column=0, columnspan=2, pady=20, padx=10, sticky="nsew")

        # Buttons (reduced thickness)
        admin_buttons = [
            ("Unlock Locker",      self.on_unlock),
            ("Change Price",       self.on_change_price),
            ("Change Color",       self.on_change_color),
            ("Change All Colors",  self.on_change_all_color),
            ("Lock The order",     self.on_lock_order),      
            ("Set Lighting mode",  self.on_set_lighting_mode),  
            ("Ventilation",        self.on_ventilation),
            ("Close Program",      self.on_close_program),
        ]

        for idx, (text, command) in enumerate(admin_buttons, start=2):
            button = tk.Button(
                self, text=text, font=("Arial", 27), command=command
            )
            # Adjust the width a bit:
            button.config(width=33, height=2)
            button.grid(row=idx, column=0, columnspan=2, padx=30, pady=10, sticky="nsew")

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
        self.buttons[self.locker_id].config(bg="#F0F0F0", state="normal")  # Reset button
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

    def on_lock_order(self):
        """Handle locking the order (NEW)."""
        self.reset_timeout()
        self.lock_order_callback()  # CALL THE NEW CALLBACK
        self.hide()

    def on_set_lighting_mode(self):
        """
        Show the LightingModeFrame when the 'Set Lighting mode' button is pressed.
        """
        self.reset_timeout()
        # Show the new LightingModeFrame
        if hasattr(self.master, "lighting_mode_frame"):
            self.master.lighting_mode_frame.show(self.locker_id)
        self.hide()

    def on_ventilation(self):
        self.reset_timeout()
        if hasattr(self.master, "ventilation_frame"):
            self.master.ventilation_frame.show()
        self.hide()

    def on_close(self):
        """Handle closing the frame via the 'X' button."""
        self.hide()

    def show(self, locker_id):
        """
        Display the AdminOptionsFrame for a specific locker.
        """
        self.set_locker_id(locker_id)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()
        self.cancel_order_callback(locker_id)

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

    def set_locker_id(self, locker_id):
        """
        Update the locker ID and refresh the label text.
        """
        self.locker_id = locker_id
        self.label.config(text=f"Locker {self.locker_id} Options")


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


        # Message content
        text_german = (
            "Leider ist das Schließfach blockiert.\n"
            "   Für Rückerstattung oder Blumen kontaktieren Sie bitte:  \n"
            "Aija: +4915782920110\n"
            "Janis: +4915757165517"
        )
        text_english = (
            "Unfortunately, the locker is jammed.\n"
            "To get a refund or flowers, please contact:\n"
            "Aija: +4915782920110\n"
            "Janis: +4915757165517"
        )

        # Labels for the German text (larger size, bold font)
        label_german = tk.Label(
            self, text=text_german, font=("Arial", 33, "bold"), bg="#FFC0C0", justify="center", wraplength=1600
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



def gamma_correct(value, gamma=2.2):
    """
    Apply gamma correction to a single 0-255 channel value.
    Returns an int in the range [0..255].
    """
    # Avoid zero-based edge case in exponent
    # but if you want to allow pure 0, remove the max(0, ...) line.
    corrected = (value / 255.0) ** (1.0 / gamma)
    return int(round(corrected * 255))

def rgb_to_hex(r, g, b, gamma=2.2):
    """
    Convert (r,g,b) to a gamma-corrected hex string.
    Ensures we never display pure black in case the LED cannot do that.
    """
    # If truly (0,0,0), we force (1,1,1) to avoid a fully black display
    if r == 0 and g == 0 and b == 0:
        r, g, b = 1, 1, 1

    # Gamma-correct each channel
    r_g = gamma_correct(r, gamma)
    g_g = gamma_correct(g, gamma)
    b_g = gamma_correct(b, gamma)

    # Also ensure we never see fully black on the GUI
    if r_g == 0 and g_g == 0 and b_g == 0:
        r_g, g_g, b_g = 1, 1, 1

    return f"#{r_g:02x}{g_g:02x}{b_g:02x}"

class RGBEntryFrame(tk.Frame):
    def __init__(self, master, locker_id, spi_handler, save_rgb_callback, timeout=60000):
        """
        Initialize the RGBEntryFrame.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.locker_id = locker_id
        self.spi_handler = spi_handler
        self.save_rgb_callback = save_rgb_callback
        self.timeout = timeout
        self.last_interaction = None

        # Variables to handle throttled SPI updates
        self._pending_color = (125, 125, 125)  # Starting color
        self._last_sent_color = None
        self._timer = None

        # Prevent frame from resizing based on its content
        self.pack_propagate(False)
        self.config(width=600, height=400)

        # Configure grid layout
        self.grid_rowconfigure(0, weight=0)  # Title + default color buttons + "X"
        self.grid_rowconfigure(1, weight=0)  # R, G, B row
        for i in range(2, 7):
            self.grid_rowconfigure(i, weight=1)  # Keypad rows
        for j in range(3):
            self.grid_columnconfigure(j, weight=1)  # 3 columns for keypad

        # ------------------- Top Frame (Title, Preset Buttons, Close) -------------------
        top_frame = tk.Frame(self, bg="#F0F0F0")
        top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=20)
        top_frame.grid_columnconfigure(0, weight=0)  # Title
        top_frame.grid_columnconfigure(1, weight=1)  # Preset color buttons
        top_frame.grid_columnconfigure(2, weight=0)  # "X" button 

        self.title_label = tk.Label(
            top_frame,
            text="RGB for Locker",
            font=("Arial", 27, "bold"),
            bg="#F0F0F0"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        preset_frame = tk.Frame(top_frame, bg="#F0F0F0")
        preset_frame.grid(row=0, column=1, sticky="e")

        self.close_button = tk.Button(
            top_frame,
            text="X",
            command=self.on_close,
            font=("Arial", 27, "bold"),
            bd=0,
            bg="#F0F0F0",
            activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=2, sticky="e")
        self.close_button.config(width=4, height=2)

        # ------------------- Input Frame (R, G, B) -------------------
        input_frame = tk.Frame(self, bg="#F0F0F0")
        input_frame.grid(row=1, column=0, columnspan=3, pady=10, padx=40, sticky="nsew")
        input_frame.grid_columnconfigure(2, weight=1)

        self.red_value = tk.StringVar()
        self.green_value = tk.StringVar()
        self.blue_value = tk.StringVar()

        # R
        tk.Label(
            input_frame, text="R:", font=("Arial", 27), bg="#F0F0F0"
        ).grid(row=0, column=0, sticky="w")

        self.red_entry = tk.Entry(
            input_frame,
            textvariable=self.red_value,
            font=("Arial", 42),
            justify="center",
            width=3
        )
        self.red_entry.grid(row=0, column=1, sticky="w", padx=(10, 20))
        self.red_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.red_entry.bind("<FocusOut>", self.on_entry_focus_out)

        self.red_scale = tk.Scale(
            input_frame,
            from_=0, to=255,
            orient="horizontal",
            command=self.on_red_scale,
            troughcolor="white",
            bg="#F0F0F0",
            width=60,
            sliderlength=60
        )
        self.red_scale.config(fg="red", highlightthickness=0)
        self.red_scale.grid(row=0, column=2, sticky="ew", padx=(0, 20))

        # G
        tk.Label(
            input_frame, text="G:", font=("Arial", 27), bg="#F0F0F0"
        ).grid(row=1, column=0, sticky="w")

        self.green_entry = tk.Entry(
            input_frame,
            textvariable=self.green_value,
            font=("Arial", 42),
            justify="center",
            width=3
        )
        self.green_entry.grid(row=1, column=1, sticky="w", padx=(10, 20))
        self.green_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.green_entry.bind("<FocusOut>", self.on_entry_focus_out)

        self.green_scale = tk.Scale(
            input_frame,
            from_=0, to=255,
            orient="horizontal",
            command=self.on_green_scale,
            troughcolor="white",
            bg="#F0F0F0",
            width=60,
            sliderlength=60
        )
        self.green_scale.config(fg="green", highlightthickness=0)
        self.green_scale.grid(row=1, column=2, sticky="ew", padx=(0, 20))

        # B
        tk.Label(
            input_frame, text="B:", font=("Arial", 27), bg="#F0F0F0"
        ).grid(row=2, column=0, sticky="w")

        self.blue_entry = tk.Entry(
            input_frame,
            textvariable=self.blue_value,
            font=("Arial", 42),
            justify="center",
            width=3
        )
        self.blue_entry.grid(row=2, column=1, sticky="w", padx=(10, 20))
        self.blue_entry.bind("<FocusIn>", self.on_entry_focus_in)
        self.blue_entry.bind("<FocusOut>", self.on_entry_focus_out)

        self.blue_scale = tk.Scale(
            input_frame,
            from_=0, to=255,
            orient="horizontal",
            command=self.on_blue_scale,
            troughcolor="white",
            bg="#F0F0F0",
            width=60,
            sliderlength=60
        )
        self.blue_scale.config(fg="blue", highlightthickness=0)
        self.blue_scale.grid(row=2, column=2, sticky="ew", padx=(0, 20))

        # Preset color buttons (including "Current")
        self.default_colors = [
            ("Current", None),
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Cyan", (0, 255, 255))
        ]
        self.color_buttons = []

        for idx, (color_name, rgb_tuple) in enumerate(self.default_colors):
            btn = tk.Button(
                preset_frame,
                text="",
                width=4,
                height=2,
                command=lambda r=rgb_tuple: self.set_color_from_button(r)
            )
            if rgb_tuple is None:
                hexcolor = "#ffffff"
            else:
                r_raw, g_raw, b_raw = rgb_tuple
                hexcolor = rgb_to_hex(r_raw, g_raw, b_raw)
            btn.config(bg=hexcolor, activebackground=hexcolor)
            btn.grid(row=0, column=idx, padx=10, sticky="e")
            self.color_buttons.append(btn)

        self.create_keypad()

        # Link up the entry changes (trace)
        self.red_value.trace_add("write", self.on_red_entry_changed)
        self.green_value.trace_add("write", self.on_green_entry_changed)
        self.blue_value.trace_add("write", self.on_blue_entry_changed)

        # Bind interactions to reset timeout
        for child in self.winfo_children():
            if isinstance(child, (tk.Button, tk.Entry)):
                child.bind("<Button-1>", self.reset_timeout)
                child.bind("<Key>", self.reset_timeout)
        for child in preset_frame.winfo_children():
            child.bind("<Button-1>", self.reset_timeout)
        for child in input_frame.winfo_children():
            if isinstance(child, (tk.Button, tk.Entry, tk.Scale)):
                child.bind("<Button-1>", self.reset_timeout)
                child.bind("<Key>", self.reset_timeout)

        self.reset_timeout()

        # Start periodic “send” timer (every 20ms)
        self.periodic_send()

    # -----------------------------------------------------------------------
    #   Periodic SPI Send (every 20ms)
    # -----------------------------------------------------------------------
    def periodic_send(self):
        """
        Sends the pending color to SPI once every 20ms if it has changed
        since the last send.
        """
        if self._pending_color != self._last_sent_color:
            if self.spi_handler:
                locker_id = self.locker_id
                r, g, b = self._pending_color
                self.spi_handler.set_led_color(locker_id, r, g, b)
                self._last_sent_color = self._pending_color

        # Schedule the next 20ms check
        self._timer = self.after(50, self.periodic_send)

    # -----------------------------------------------------------------------
    #   Focus In/Out for each Entry
    # -----------------------------------------------------------------------
    def on_entry_focus_in(self, event):
        event.widget.delete(0, tk.END)

    def on_entry_focus_out(self, event):
        text_value = event.widget.get().strip()
        if not text_value:
            event.widget.delete(0, tk.END)
            event.widget.insert(0, "0")
        else:
            ivalue = self.validate_rgb(text_value)
            event.widget.delete(0, tk.END)
            event.widget.insert(0, str(ivalue))

    # -----------------------------------------------------------------------
    #   Keypad creation
    # -----------------------------------------------------------------------
    def create_keypad(self):
        buttons = [
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('4', 3, 0), ('5', 3, 1), ('6', 3, 2),
            ('7', 4, 0), ('8', 4, 1), ('9', 4, 2),
            ('Clear', 5, 0), ('0', 5, 1), ('Save', 5, 2)
        ]
        for (text, row, col) in buttons:
            if text == "Clear":
                command = self.clear_inputs
            elif text == "Save":
                command = self.save_rgb
            else:
                command = lambda t=text: self.on_number(t)
            button = tk.Button(
                self, text=text, font=("Arial", 27),
                command=command, bd=2, relief="raised",
                bg="#D9D9D9", activebackground="#BEBEBE"
            )
            button.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
            button.config(width=7, height=3)

    # -----------------------------------------------------------------------
    #   Scale callbacks -> update corresponding Entry
    # -----------------------------------------------------------------------
    def on_red_scale(self, val):
        self.reset_timeout()
        self.red_value.set(str(int(float(val))))

    def on_green_scale(self, val):
        self.reset_timeout()
        self.green_value.set(str(int(float(val))))

    def on_blue_scale(self, val):
        self.reset_timeout()
        self.blue_value.set(str(int(float(val))))

    # -----------------------------------------------------------------------
    #   Entry trace callbacks -> update corresponding Scale and “pending color”
    # -----------------------------------------------------------------------
    def on_red_entry_changed(self, *args):
        val = self.validate_rgb(self.red_value.get())
        self.red_scale.set(val)
        self.update_current_color_button()
        self.update_led_color()  # Just updates _pending_color now

    def on_green_entry_changed(self, *args):
        val = self.validate_rgb(self.green_value.get())
        self.green_scale.set(val)
        self.update_current_color_button()
        self.update_led_color()

    def on_blue_entry_changed(self, *args):
        val = self.validate_rgb(self.blue_value.get())
        self.blue_scale.set(val)
        self.update_current_color_button()
        self.update_led_color()

    # -----------------------------------------------------------------------
    #   Store the latest color in self._pending_color (instead of sending immediately)
    # -----------------------------------------------------------------------
    def update_led_color(self):
        r = self.validate_rgb(self.red_value.get())
        g = self.validate_rgb(self.green_value.get())
        b = self.validate_rgb(self.blue_value.get())
        self._pending_color = (r, g, b)

    def validate_rgb(self, value):
        try:
            ivalue = int(value)
        except ValueError:
            return 0
        return max(0, min(255, ivalue))

    def update_current_color_button(self):
        r = self.validate_rgb(self.red_value.get())
        g = self.validate_rgb(self.green_value.get())
        b = self.validate_rgb(self.blue_value.get())

        hexcolor = rgb_to_hex(r, g, b)
        self.color_buttons[0].config(bg=hexcolor, activebackground=hexcolor)

    def set_color_from_button(self, rgb_tuple):
        if rgb_tuple is None:
            # "Current" button—do nothing special
            return
        r, g, b = rgb_tuple
        self.red_value.set(str(r))
        self.green_value.set(str(g))
        self.blue_value.set(str(b))

    # -----------------------------------------------------------------------
    #   Keypad number + Clear + Save
    # -----------------------------------------------------------------------
    def on_number(self, number):
        self.reset_timeout()
        focused = self.focus_get()
        if focused in (self.red_entry, self.green_entry, self.blue_entry):
            current = focused.get()
            if len(current) < 3 and number.isdigit():
                focused.insert(tk.END, number)

    def clear_inputs(self):
        self.reset_timeout()
        self.red_value.set("0")
        self.green_value.set("0")
        self.blue_value.set("0")

    def save_rgb(self):
        self.reset_timeout()
        try:
            red   = self.validate_rgb(self.red_value.get())
            green = self.validate_rgb(self.green_value.get())
            blue  = self.validate_rgb(self.blue_value.get())
        except Exception as e:
            print(f"Error converting RGB inputs: {e}", file=sys.stderr)
            return

        # NEW – hand the colour triplet back to the main app
        self.save_rgb_callback(self.locker_id, red, green, blue)

        # The SPI “periodic_send” loop is still running, so the LEDs
        # keep receiving _pending_color exactly as before.
        print("Success: RGB values queued for saving.")
        self.hide()




    def on_close(self):
        self.hide()

    def show(self, locker_id):
        self.locker_id = locker_id
        try:
            with open("lockers.json", "r") as file:
                lockers = json.load(file)
        except FileNotFoundError:
            lockers = {}

        if locker_id == 255:
            locker = lockers.get("1", {"red":125, "green":125, "blue":125})
            title = "RGB for All Lockers"
        else:
            locker = lockers.get(str(locker_id), {"red":125, "green":125, "blue":125})
            title = f"RGB for Locker {locker_id}"

        self.red_value.set(str(locker.get("red", 125)))
        self.green_value.set(str(locker.get("green", 125)))
        self.blue_value.set(str(locker.get("blue", 125)))
        self.title_label.config(text=title)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def show_all(self):
        self.show(255)

    def hide(self):
        self.place_forget()
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    # -----------------------------------------------------------------------
    #   Timeout handling
    # -----------------------------------------------------------------------
    def reset_timeout(self, event=None):
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        self.hide()


class PaymentPopupFrame(tk.Frame):
    def __init__(self, master, cancel_callback, timeout=40000):
        """
        Initialize the PaymentPopupFrame.

        :param master: Parent widget.
        :param cancel_callback: Function to cancel the payment.
        :param timeout: Timeout duration in milliseconds.
        """
        super().__init__(master, bg="#1e6039")  # Background color set to #1e6039
        self.master = master
        self.cancel_callback = cancel_callback
        self.timeout = timeout
        self.last_interaction = None

        # Configure grid to layout widgets properly
        self.grid_rowconfigure(0, weight=1)  # For the main message
        self.grid_columnconfigure(0, weight=1)

        # Main message label
        self.message_label = tk.Label(
            self,
            text="Bitte folgen Sie den Anweisungen im Terminal!",  # Translated to German
            font=("Arial", 48, "bold"),  # Font size doubled from 24 to 48
            bg="#1e6039",                # Text background color set to match frame
            fg="#8bcbb9",                # Text color set to #8bcbb9
            wraplength=800,              # Wraplength doubled from 400 to 800
            justify="center"
        )
        self.message_label.grid(row=0, column=0, padx=40, pady=80)  # Padding adjusted for larger size

        # Note on size adjustments
        # To further adjust the size, modify the 'font' and 'wraplength' parameters above.
        # For example, to increase the font size, change (Arial, 48, "bold") to a larger size.
        # Similarly, adjust 'wraplength' to ensure the text fits well within the frame.

        # Bind interactions to reset timeout (optional, since there are no buttons)
        self.message_label.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_cancel(self):
        """Handle cancellation via the 'cancel_callback'."""
        print("PaymentPopupFrame: Cancel action triggered.")  # Debugging
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
        #print("PaymentPopupFrame: Frame hidden.")  # Debugging

    def reset_timeout(self, event=None):
        """Reset the timeout timer upon user interaction."""
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)
        #print("PaymentPopupFrame: Timeout reset.")  # Debugging

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



class SetPinFrame(tk.Frame):
    """
    A frame for entering a 6-digit PIN in two modes:
      1) is_first_way=True => calls a callback (handle_lock_order_pin)
      2) is_first_way=False => returns the entered pin to the caller (reserved locker scenario)
    """

    def __init__(self, master, callback=None, timeout=30000):
        """
        :param master: The main application (VendingMachineApp).
        :param callback: The function to call if is_first_way=True. 
                         e.g. handle_lock_order_pin(locker_id, pin).
        :param timeout: Timeout for user inactivity in ms.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.callback = callback
        self.timeout = timeout
        self.last_interaction = None

        # For storing state
        self.locker_id = None
        self.is_first_way = True
        self.result_var = None  # used to return the pin if is_first_way=False

        # Grid layout
        self.grid_rowconfigure(0, weight=0)  # "X" button
        self.grid_rowconfigure(1, weight=0)  # Title
        self.grid_rowconfigure(2, weight=1)  # PIN entry
        for i in range(3, 8):
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

        # Title label
        self.title_label = tk.Label(
            self, text="Enter 6 digit pin", font=("Arial", 36, "bold"), bg="#F0F0F0"
        )
        self.title_label.grid(row=1, column=0, columnspan=3, pady=10)

        # PIN entry
        self.entered_pin = tk.StringVar()
        self.entry_display = tk.Entry(
            self, textvariable=self.entered_pin, font=("Arial", 54),
            justify="center", show="*"
        )
        self.entry_display.grid(row=2, column=0, columnspan=3, pady=30, padx=90)

        # Numeric keypad
        buttons = [
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2),
            ('4', 4, 0), ('5', 4, 1), ('6', 4, 2),
            ('7', 5, 0), ('8', 5, 1), ('9', 5, 2),
            ('0', 6, 1), ('Enter', 6, 2), ('Clear', 6, 0)
        ]
        for (text, row, col) in buttons:
            if text == "Enter":
                btn = tk.Button(self, text=text, font=("Arial", 27), command=self.on_enter)
            elif text == "Clear":
                btn = tk.Button(self, text=text, font=("Arial", 27), command=self.on_clear)
            else:
                btn = tk.Button(
                    self, text=text, font=("Arial", 27),
                    command=lambda t=text: self.on_number(t)
                )
            btn.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
            btn.config(width=7, height=3)

        # Bind to reset timeout
        self.entry_display.bind("<Key>", self.reset_timeout)
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_number(self, number):
        """If 7th digit => clear everything."""
        self.reset_timeout()
        current_pin = self.entered_pin.get()
        if len(current_pin) == 6:
            self.entered_pin.set("")
            return
        self.entered_pin.set(current_pin + number)

    def on_clear(self):
        """Clear the PIN."""
        self.reset_timeout()
        self.entered_pin.set("")

    def on_enter(self):
        """
        If exactly 6 digits:
          - is_first_way=True => calls self.callback(locker_id, pin).
          - is_first_way=False => sets result_var => unblocks show_and_get_pin
        Else => close entire app.
        """
        self.reset_timeout()
        pin = self.entered_pin.get()
        if len(pin) != 6:
            # Not 6 => close entire app
            self.on_clear()
            return

        if self.is_first_way:
            # "First way" => callback approach
            if self.callback:
                self.callback(self.locker_id, pin)
        else:
            # "Second way" => return PIN to the caller
            self.result_var.set(pin)
        self.hide()

    def on_close(self):
        """User clicked X => hide + set result to "" if second way."""
        if not self.is_first_way and self.result_var:
            self.result_var.set("")  # means "cancel"
        self.hide()

    def show(self, locker_id, is_first_way=True):
        """
        Non-blocking version. If first way => calls callback on success,
        if second way => does no callback.
        """
        self.locker_id = locker_id
        self.is_first_way = is_first_way
        self.entered_pin.set("")
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def show_and_get_pin(self, locker_id):
        """
        A blocking approach => returns pin or None.
        This is for "second way" usage.
        """
        self.locker_id = locker_id
        self.is_first_way = False
        self.entered_pin.set("")
        self.result_var = tk.StringVar(value="")  # empty means not done

        # Show frame
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

        # Block
        self.wait_variable(self.result_var)

        # Once unblocked => read
        final_pin = self.result_var.get()  # could be "" or 6-digit
        self.hide()

        return final_pin if final_pin else None

    def hide(self):
        """Hide the frame."""
        self.place_forget()
        self.entered_pin.set("")
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        """Timeout => same as closing => hide + set "" if second way."""
        self.on_close()

class LightingModeFrame(tk.Frame):
    def __init__(self, master, spi_handler, timeout=60000):
        """
        Initialize the LightingModeFrame.
        """
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.timeout = timeout
        self.spi_handler = spi_handler
        self.last_interaction = None
        # New variables for mode tracking:
        self.previous_mode = None
        self.chosen_mode = None

        # Increase the overall size of the frame
        self.config(width=800, height=600)

        # Configure grid layout: reserve rows for title, mode buttons, and bottom buttons.
        self.grid_rowconfigure(0, weight=0)  # "X" button row
        self.grid_rowconfigure(1, weight=0)  # Title row
        for i in range(2, 7):
            self.grid_rowconfigure(i, weight=1)  # Mode button rows
        self.grid_rowconfigure(7, weight=0)  # Bottom row for Cancel/Save
        for i in range(2):
            self.grid_columnconfigure(i, weight=1)

        # "X" button to close the frame (acts like Cancel)
        self.close_button = tk.Button(
            self, text="X", command=self.on_close, font=("Arial", 27, "bold"), bd=0,
            bg="#F0F0F0", activebackground="#F0F0F0"
        )
        self.close_button.grid(row=0, column=1, sticky="ne", padx=20, pady=20)
        self.close_button.config(width=4, height=2)

        # Frame Title
        self.label = tk.Label(
            self, text="Lighting Mode Options", font=("Arial", 36, "bold"), bg="#F0F0F0"
        )
        self.label.grid(row=1, column=0, columnspan=2, pady=20, padx=10, sticky="nsew")

        # Mode Buttons – each sets the mode immediately and stores it in self.chosen_mode.
        mode_buttons = [
            ("Mode1 - V-day", self.on_mode1),
            ("Mode2 - Disco", self.on_mode2),
            ("Mode3 - Psychedelic", self.on_mode3),
            ("Mode4 - Welcom", self.on_mode4),
            ("Mode5 - Solid Disco", self.on_mode5),
        ]
        for idx, (text, command) in enumerate(mode_buttons, start=2):
            button = tk.Button(
                self, text=text, font=("Arial", 27), command=command
            )
            button.config(width=40, height=2)
            button.grid(row=idx, column=0, columnspan=2, padx=30, pady=10, sticky="nsew")

        # Bottom buttons: Cancel (left) and Save (right)
        self.cancel_button = tk.Button(
            self, text="Cancel", font=("Arial", 27), command=self.on_cancel,
            bg="#D9D9D9", activebackground="#BEBEBE"
        )
        self.cancel_button.config(width=20, height=2)
        self.cancel_button.grid(row=7, column=0, padx=30, pady=20, sticky="nsew")

        self.save_button = tk.Button(
            self, text="Save", font=("Arial", 27), command=self.on_save,
            bg="#D9D9D9", activebackground="#BEBEBE"
        )
        self.save_button.config(width=20, height=2)
        self.save_button.grid(row=7, column=1, padx=30, pady=20, sticky="nsew")

        # Bind interactions to reset timeout
        for child in self.winfo_children():
            if isinstance(child, tk.Button):
                child.bind("<Button-1>", self.reset_timeout)

        self.reset_timeout()

    def on_mode1(self):
        """Handle selecting Mode1."""
        self.chosen_mode = 1
        self.spi_handler.set_led_color(255, 0, 0, 0, 1)
        self.reset_timeout()
        print("Mode1 selected.")

    def on_mode2(self):
        """Handle selecting Mode2."""
        self.chosen_mode = 2
        self.spi_handler.set_led_color(255, 0, 0, 0, 2)
        self.reset_timeout()
        print("Mode2 selected.")

    def on_mode3(self):
        """Handle selecting Mode3."""
        self.chosen_mode = 3
        self.spi_handler.set_led_color(255, 0, 0, 0, 3)
        self.reset_timeout()
        print("Mode3 selected.")

    def on_mode4(self):
        """Handle selecting Mode4."""
        self.chosen_mode = 4
        self.spi_handler.set_led_color(255, 0, 0, 0, 4)
        self.reset_timeout()
        print("Mode4 selected.")

    def on_mode5(self):
        """Handle selecting Mode5."""
        self.chosen_mode = 5
        self.spi_handler.set_led_color(255, 0, 0, 0, 5)
        self.reset_timeout()
        print("Mode5 selected.")

    def on_cancel(self):
        """
        Cancel the change:
         - Check lockers.json for the original LED color values
         - Reapply those values to all lockers
         - Close the frame.
        """
        try:
            with open("lockers.json", "r") as file:
                lockers = json.load(file)
        except Exception as e:
            print(f"Error reading lockers.json: {e}")
            self.hide()
            return

        # For each locker, reapply the stored RGB values with full mode (0xFF)
        for locker_id, locker in lockers.items():
            red = locker.get("red", 125)
            green = locker.get("green", 125)
            blue = locker.get("blue", 125)
            try:
                locker_number = int(locker_id)
            except ValueError:
                continue
            self.spi_handler.set_led_color(locker_number, red, green, blue, 0xFF)
            time.sleep(0.05)
        print("Reverted to original colors for all lockers from lockers.json.")
        self.hide()

    def on_save(self):
        """
        Save the change:
         - Keep the chosen mode (already set immediately when a mode button was pressed)
         - Close the frame.
        """
        print(f"Mode {self.chosen_mode} saved.")
        self.hide()

    def on_close(self):
        """Close the frame (acts like Cancel)."""
        self.on_cancel()

    def show(self, locker_id, current_mode=None):
        """
        Display the LightingModeFrame in the center of the screen.
        
        :param locker_id: Not used for lighting mode but kept for consistency.
        :param current_mode: The current lighting mode; if not provided, default to 1.
        """
        if current_mode is None:
            current_mode = 1  # Default mode if none is provided
        self.locker_id = locker_id
        self.previous_mode = current_mode
        self.chosen_mode = current_mode  # Default to current mode if no change is made.
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def hide(self):
        """Hide the LightingModeFrame."""
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
        """On timeout, revert changes and close the frame."""
        self.on_cancel()


class VentilationFrame(tk.Frame):
    """
    A large frame that manages 7 toggle switches: Fan1, Fan2, Fan3,
    Heat1, Heat2, Heat3, and Auto.

    - Reads logs/fan.txt (creating if missing) in show().
    - Applies that mode to toggles.
    - Whenever a toggle is pressed, we compute the new mode,
      send it via SPI, and update logs/fan.txt.
    - Pressing "Save" also does the same, then hides the frame.

    Bit assignments in manual mode (0..63):
        bit 0 => Fan1
        bit 1 => Fan2
        bit 2 => Fan3
        bit 3 => Heat1
        bit 4 => Heat2
        bit 5 => Heat3

    If mode == 255, that is 'Auto' => all fans/heats OFF.
    """

    def __init__(self, master, spi_handler, timeout=60000):
        super().__init__(master, bg="#F0F0F0")
        self.master = master
        self.spi_handler = spi_handler
        self.timeout = timeout
        self.last_interaction = None

        # Increase the overall frame size significantly
        self.config(width=1280, height=900)
        # Prevent the frame from auto-shrinking
        self.pack_propagate(False)
        self.grid_propagate(False)

        # We have 3 rows:
        #   row=0 => Title + Close "X"
        #   row=1 => toggles (expand)
        #   row=2 => Save button
        #
        # Give row=0 and row=2 a fixed-ish minimal height,
        # Let row=1 (toggles) expand to fill the rest.
        self.grid_rowconfigure(0, minsize=60, weight=0)
        self.grid_rowconfigure(1, weight=1)   # toggles
        self.grid_rowconfigure(2, minsize=60, weight=0)

        # 3 columns (0..2):
        #   col=0..1 => for the title
        #   col=2    => for the close button
        for c in range(3):
            self.grid_columnconfigure(c, weight=1)

        # -------------------- Row=0: Title & Close "X" --------------------
        self.title_label = tk.Label(
            self,
            text="Ventilation & Heating Control",
            font=("Arial", 36, "bold"),
            bg="#F0F0F0",
            anchor="center",
            justify="center"
        )
        # Spans columns 0..1 for centering
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.close_button = tk.Button(
            self,
            text="X",
            command=self.on_close,
            font=("Arial", 27, "bold"),
            bd=0,
            bg="#F0F0F0",
            activebackground="#F0F0F0",
            width=3,
            height=1
        )
        self.close_button.grid(row=0, column=2, sticky="e", padx=10, pady=10)

        # -------------------- Row=1: Toggles Frame --------------------
        toggles_frame = tk.Frame(self, bg="#F0F0F0")
        toggles_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)

        # Inside toggles_frame, we have 7 rows (Fan1..3, Heat1..3, Auto).
        # We'll keep 4 columns (0..3).
        #  col=0,3 => weight=1 to push content to the center
        #  col=1 => label, col=2 => button
        for col in range(4):
            toggles_frame.grid_columnconfigure(col, weight=(1 if col in [0, 3] else 0))

        # Make each toggle row at least 100 px tall,
        # so there's enough space for a big button.
        for r in range(7):
            toggles_frame.grid_rowconfigure(r, minsize=100, weight=1)

        # Track toggles
        self.fan1_on = False
        self.fan2_on = False
        self.fan3_on = False
        self.heat1_on = False
        self.heat2_on = False
        self.heat3_on = False
        self.auto_on = False

        # Create toggles in rows 0..6
        self.fan1_switch  = self.create_toggle_row(toggles_frame, 0, "Fan 1",  self.toggle_fan1)
        self.fan2_switch  = self.create_toggle_row(toggles_frame, 1, "Fan 2",  self.toggle_fan2)
        self.fan3_switch  = self.create_toggle_row(toggles_frame, 2, "Fan 3",  self.toggle_fan3)
        self.heat1_switch = self.create_toggle_row(toggles_frame, 3, "Heat 1", self.toggle_heat1)
        self.heat2_switch = self.create_toggle_row(toggles_frame, 4, "Heat 2", self.toggle_heat2)
        self.heat3_switch = self.create_toggle_row(toggles_frame, 5, "Heat 3", self.toggle_heat3)
        self.auto_switch  = self.create_toggle_row(toggles_frame, 6, "Auto",   self.toggle_auto)

        # -------------------- Row=2: Save Button --------------------
        self.save_button = tk.Button(
            self,
            text="Save",
            font=("Arial", 36),  # bigger font
            command=self.on_save
        )
        # Fill horizontally; add thickness with ipady
        self.save_button.grid(
            row=2, column=0, columnspan=3,
            sticky="nsew", padx=10, pady=5, ipady=20
        )

        # Bind interactions for auto-close
        self.bind_all("<Button-1>", self.reset_timeout)
        self.reset_timeout()

    def create_toggle_row(self, parent, row_index, label_text, toggle_func):
        """
        Create a toggle row in toggles_frame.
        Label at col=1, Button at col=2 => columns 0 & 3 push them to center.
        """
        lbl = tk.Label(
            parent,
            text=label_text,
            font=("Arial", 36),
            bg="#F0F0F0",
            anchor="e"
        )
        lbl.grid(row=row_index, column=1, sticky="e", padx=5, pady=5)

        # Large font + ipady=50 => extra thick button
        btn = tk.Button(
            parent,
            text="OFF",
            font=("Arial", 42),
            bg="red",
            fg="white",
            activebackground="red",
            activeforeground="white",
            command=toggle_func,
            width=6
        )
        btn.grid(row=row_index, column=2, sticky="w", padx=5, pady=5, ipady=50)
        return btn

    # ------------------- Toggling Logic + Immediate SPI Send -------------------

    def toggle_fan1(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.fan1_on = not self.fan1_on
        self.update_switch(self.fan1_switch, self.fan1_on)
        self._update_and_send()

    def toggle_fan2(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.fan2_on = not self.fan2_on
        self.update_switch(self.fan2_switch, self.fan2_on)
        self._update_and_send()

    def toggle_fan3(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.fan3_on = not self.fan3_on
        self.update_switch(self.fan3_switch, self.fan3_on)
        self._update_and_send()

    def toggle_heat1(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.heat1_on = not self.heat1_on
        self.update_switch(self.heat1_switch, self.heat1_on)
        self._update_and_send()

    def toggle_heat2(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.heat2_on = not self.heat2_on
        self.update_switch(self.heat2_switch, self.heat2_on)
        self._update_and_send()

    def toggle_heat3(self):
        if self.auto_on:
            self.auto_on = False
            self.update_switch(self.auto_switch, self.auto_on)
        self.heat3_on = not self.heat3_on
        self.update_switch(self.heat3_switch, self.heat3_on)
        self._update_and_send()

    def toggle_auto(self):
        self.auto_on = not self.auto_on
        self.update_switch(self.auto_switch, self.auto_on)

        if self.auto_on:
            self.fan1_on = False
            self.fan2_on = False
            self.fan3_on = False
            self.heat1_on = False
            self.heat2_on = False
            self.heat3_on = False
            self.update_switch(self.fan1_switch,  self.fan1_on)
            self.update_switch(self.fan2_switch,  self.fan2_on)
            self.update_switch(self.fan3_switch,  self.fan3_on)
            self.update_switch(self.heat1_switch, self.heat1_on)
            self.update_switch(self.heat2_switch, self.heat2_on)
            self.update_switch(self.heat3_switch, self.heat3_on)

        self._update_and_send()

    def update_switch(self, switch_btn, is_on):
        """Update the text/color of a switch button for ON/OFF states."""
        if is_on:
            switch_btn.config(
                text="ON",
                bg="green",
                activebackground="green",
                fg="white",
                activeforeground="white"
            )
        else:
            switch_btn.config(
                text="OFF",
                bg="red",
                activebackground="red",
                fg="white",
                activeforeground="white"
            )

    # ------------------- on_save + Immediate Updates -------------------

    def on_save(self):
        """
        1) compute mode from toggles
        2) send via SPI
        3) write logs/fan.txt
        4) hide()
        """
        mode = self._compute_mode_from_toggles()
        print(f"[VentilationFrame] mode = {mode}")

        if self.spi_handler:
            self.spi_handler.send_command(0x04, [mode, 0xFF, 0xFF, 0xFF, 0xFF])

        self._write_fan_file(mode)
        self.hide()

    def _update_and_send(self):
        """
        Whenever a toggle changes, compute the new mode,
        send it over SPI, and save to fan.txt immediately.
        """
        mode = self._compute_mode_from_toggles()
        print(f"[VentilationFrame] Toggled => mode = {mode}")

        if self.spi_handler:
            self.spi_handler.send_command(0x04, [mode, 0xFF, 0xFF, 0xFF, 0xFF])

        self._write_fan_file(mode)

    def _compute_mode_from_toggles(self):
        """
        Compute a single integer (0..63) or 255 if auto is on.
          bit 0 => fan1_on
          bit 1 => fan2_on
          bit 2 => fan3_on
          bit 3 => heat1_on
          bit 4 => heat2_on
          bit 5 => heat3_on
        Auto => 255
        """
        if self.auto_on:
            return 255

        mode = 0
        if self.fan1_on:   mode |= 1   # bit 0
        if self.fan2_on:   mode |= 2   # bit 1
        if self.fan3_on:   mode |= 4   # bit 2
        if self.heat1_on:  mode |= 8   # bit 3
        if self.heat2_on:  mode |= 16  # bit 4
        if self.heat3_on:  mode |= 32  # bit 5

        return mode

    # ------------------- Show / Hide / Timeout -------------------

    def on_close(self):
        self.hide()

    def show(self):
        """Read logs/fan.txt, apply it, then display the frame."""
        saved_mode = self._read_fan_file()
        self._apply_mode_to_toggles(saved_mode)
        self.place(relx=0.5, rely=0.5, anchor="center")
        self.lift()
        self.focus_set()
        self.reset_timeout()

    def hide(self):
        """Hide the frame and cancel any timeout."""
        self.place_forget()
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
            self.last_interaction = None

    def reset_timeout(self, event=None):
        if self.last_interaction:
            self.after_cancel(self.last_interaction)
        self.last_interaction = self.after(self.timeout, self.on_timeout)

    def on_timeout(self):
        self.hide()

    # ------------------- File I/O Helpers -------------------

    def _read_fan_file(self):
        """
        Reads a single integer from logs/fan.txt.
        If the file doesn't exist, create it with '0' and return 0.
        """
        path = "logs/fan.txt"
        if not os.path.exists(path):
            os.makedirs("logs", exist_ok=True)
            with open(path, "w") as f:
                f.write("0\n")
            return 0

        try:
            with open(path, "r") as f:
                return int(f.read().strip())
        except:
            return 0

    def _write_fan_file(self, mode):
        """
        Writes the given mode (0..63 or 255) to logs/fan.txt.
        """
        path = "logs/fan.txt"
        os.makedirs("logs", exist_ok=True)
        with open(path, "w") as f:
            f.write(f"{mode}\n")

    def _apply_mode_to_toggles(self, mode):
        """
        Given a mode integer (0..63 or 255),
        set (fan1_on, fan2_on, fan3_on, heat1_on, heat2_on, heat3_on, auto_on),
        then update the switch buttons.
        """
        if mode == 255:
            self.auto_on = True
            self.fan1_on = False
            self.fan2_on = False
            self.fan3_on = False
            self.heat1_on = False
            self.heat2_on = False
            self.heat3_on = False
        else:
            self.auto_on = False
            self.fan1_on  = bool(mode & 1)    
            self.fan2_on  = bool(mode & 2)
            self.fan3_on  = bool(mode & 4)
            self.heat1_on = bool(mode & 8)
            self.heat2_on = bool(mode & 16)
            self.heat3_on = bool(mode & 32)

        self.update_switch(self.fan1_switch,  self.fan1_on)
        self.update_switch(self.fan2_switch,  self.fan2_on)
        self.update_switch(self.fan3_switch,  self.fan3_on)
        self.update_switch(self.heat1_switch, self.heat1_on)
        self.update_switch(self.heat2_switch, self.heat2_on)
        self.update_switch(self.heat3_switch, self.heat3_on)
        self.update_switch(self.auto_switch,  self.auto_on)