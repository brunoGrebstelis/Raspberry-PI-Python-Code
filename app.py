# app.py
import tkinter as tk
from tkinter import messagebox, TclError
import time
import os
from admin_frames import AdminOptionsFrame, PriceEntryFrame, InformationFrame, RGBEntryFrame, PaymentPopupFrame, PinEntryFrame
from utils import load_locker_data, save_locker_data, send_command, log_event
from spi_handler import SPIHandler
from scheduler import Scheduler
from mdb_handler import MDBHandler
import threading
from gui import (
    size, 
    load_images, 
    create_locker_buttons, 
    create_pay_button,
    create_close_button,
    create_title_bar
)

class VendingMachineApp(tk.Tk):
    def __init__(self, bot_queue):
        super().__init__()
        self.bot_queue = bot_queue

        # Remove window decorations
        self.overrideredirect(True)

        size(self)
        self.selected_locker = None
        self.locker_data = load_locker_data()

        # Initialize the scheduler
        self.scheduler = Scheduler()
        self.scheduler.start()

        # Boolean to enable or disable PIN check on exit
        self.require_exit_pin = False  # Set to False to disable PIN verification on exit

        # Load images 
        load_images(self)

        # Initialize all frames but keep them hidden initially
        self.pin_entry_frame = PinEntryFrame(self, self.on_pin_success)
        self.pin_entry_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.pin_entry_frame.hide()

        self.admin_options_frame = AdminOptionsFrame(
            self, 
            locker_id=None,  # Will set when showing
            unlock_callback=self.unlock_locker,
            price_callback=self.change_price_callback,
            locker_data=self.locker_data,
            buttons=None,  # Will set when showing
            save_callback=save_locker_data,
            spi_handler=None,  # Will set after SPIHandler initialization
            close_program_callback=self.on_close
        )
        self.admin_options_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.admin_options_frame.hide()

        self.price_entry_frame = PriceEntryFrame(self, locker_id=None, save_price_callback=self.save_price_and_update_spi)
        self.price_entry_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.price_entry_frame.hide()

        self.rgb_entry_frame = RGBEntryFrame(self, locker_id=None, spi_handler=None)  # Will set spi_handler later
        self.rgb_entry_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.rgb_entry_frame.hide()

        self.payment_popup_frame = PaymentPopupFrame(self, cancel_callback=self.cancel_transaction)
        self.payment_popup_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.payment_popup_frame.hide()

        self.information_frame = InformationFrame(self)
        self.information_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.information_frame.hide()

        # SPIHandler initialization with error handling
        try:
            self.spi_handler = SPIHandler(bus=0, device=0, speed_hz=500000)
            self.spi_enabled = True
            print("SPI initialized successfully.")
            self.transfer_rgb_to_stm32()
            self.transfer_prices_to_stm32()

            # Assign SPI handler to RGBEntryFrame and AdminOptionsFrame
            self.rgb_entry_frame.spi_handler = self.spi_handler
            self.admin_options_frame.spi_handler = self.spi_handler

        except (ImportError, FileNotFoundError, AttributeError) as e:
            self.spi_handler = None
            self.spi_enabled = False
            print(f"SPI not available on this system: {e}")

        self.protocol("WM_DELETE_WINDOW", self.on_close)  # Ensure SPI is closed on exit

        self.mdb_handler = MDBHandler(port="/dev/ttyACM0", debug=True)
        try:
            self.mdb_handler.init_serial()
            self.mdb_handler.init_devices()
        except Exception as e:
            #messagebox.showerror("Error", f"MDB Initialization Failed: {e}")
            self.mdb_handler = None

        # Create custom title bar
        create_title_bar(self)



        # Setup buttons
        create_locker_buttons(self)

        # Create PAY button
        create_pay_button(self)

        # Create custom window control buttons
        create_close_button(self)

        # Keyboard listener for Escape key
        self.bind("<Key>", self.keyboard_listener)



    def select_locker(self, locker_id):
        if self.selected_locker is not None:
            self.buttons[self.selected_locker].config(bg="#C3C3C3", activebackground="#C3C3C3")
        self.selected_locker = locker_id
        self.buttons[locker_id].config(bg="green", activebackground="green")


    def process_payment(self):
        """Process payment when the PAY button is clicked."""
        if self.selected_locker is None:
            #messagebox.showwarning("No Selection", "Please select a locker before paying.")
            return
        
        self.pay_button.configure(state="disabled")

        locker_id = self.selected_locker
        price = self.locker_data[str(locker_id)]["price"]
        product_code = locker_id  # Use locker_id as the product code for vending.
        self.payment_success = False
        self.payment_canceled = False

        # Step 1: Create the popup in the main thread
        self.payment_popup_frame.show()

        def payment_logic():
            """Background thread for payment process."""
            try:
                # Verify the reader connection
                if not self.mdb_handler:
                    raise ConnectionError("MDB Handler is not initialized.")

                try:
                    self.mdb_handler.write2Serial("D,STATUS")
                    response = self.mdb_handler.readNWait()
                    if not response or "RESET" in response:
                        print("Card reader is resetting. Attempting reinitialization...")
                        self.mdb_handler.initserial()
                        self.mdb_handler.init_devices()
                        print("Card reader reinitialized successfully.")
                except Exception as reinit_error:
                    print(f"Failed to reinitialize card reader: {reinit_error}")
                    #messagebox.showerror("Reader Disconnected", "Card reader is disconnected or unresponsive.")
                    return  # Exit early if reinitialization fails

                print(f"Requesting payment for Locker {locker_id} with Price {price}€...")

                # Attempt Direct Vend
                direct_vend = self.mdb_handler.detect_direct_vend(str(price), str(product_code))
                if direct_vend:
                    print("Direct Vend detected. Waiting for transaction confirmation...")
                    for i in range(self.mdb_handler.VEND_TIMEOUT):
                        if self.payment_canceled:  # Check if the user canceled
                            print("Payment process canceled.")
                            return

                        res = self.mdb_handler.readNWait()
                        print(res)
                        if "d,STATUS,RESULT,1" in res:  # Success confirmation
                            self.payment_success = True
                            self.mdb_handler.endTransaction(str(price), str(product_code), res)
                            break
                        elif "d,STATUS,RESULT,-1" in res:  # Canceled by customer
                            print("Payment canceled by the customer.")
                            self.mdb_handler.cancelTransaction()
                            #messagebox.showinfo("Payment Canceled", "Payment was canceled by the customer.")
                            return
                        elif i == self.mdb_handler.VEND_TIMEOUT - 1:
                            self.mdb_handler.cancelTransaction()
                            raise TimeoutError("Transaction timed out.")
                        else:
                            time.sleep(1)
                else:
                    print("Direct Vend not supported. Proceeding with Normal Vend...")
                    if self.mdb_handler.normal_vend(str(price), str(product_code)):
                        self.payment_success = True
                    else:
                        raise ValueError("Normal Vend failed or insufficient funds.")

                if self.payment_success:
                    print("Payment successful. Updating locker status...")
                    self.locker_data[str(locker_id)]["status"] = False  # Set locker as unavailable
                    save_locker_data(self.locker_data)

                    self.buttons[locker_id].config(state="disabled")
                    self.selected_locker = None
                    self.buttons[locker_id].config(bg="#C3C3C3", activebackground="#C3C3C3")

                    self.unlock_locker(locker_id)
                    log_event(locker_id, price)
                    #messagebox.showinfo("Success", f"Locker {locker_id} unlocked successfully!")
                            # We can send a message to the queue
                    message = {
                        "chat_id": None,  # or a known chat ID if you prefer
                        "text": f"Locker {locker_id} purchased for {price}€!"
                    }
                    self.bot_queue.put(message)
                    self.after(0, self.payment_popup_frame.hide)
                else:
                    raise ValueError("Payment verification failed. Locker will not be unlocked.")

            except (ConnectionError, TimeoutError, ValueError) as e:
                print(f"Payment Error: {e}")
                #messagebox.showerror("Payment Failed", str(e))

            except Exception as e:
                print(f"Unexpected Error: {e}")
                #messagebox.showerror("Error", f"An unexpected error occurred: {e}")

            finally:
                # Ensure the popup is closed if not already
                self.pay_button.configure(state="normal")
                self.after(0, self.payment_popup_frame.hide)
                print("Payment process finished.")

        # Step 2: Run the payment logic in a background thread
        threading.Thread(target=payment_logic, daemon=True).start()




    def cancel_transaction(self):
        """Handle cancellation of the payment process."""
        print("cancel_transaction called")  # Debugging statement

        # Cancel the transaction with the MDB handler
        if self.mdb_handler:
            try:
                self.mdb_handler.cancelTransaction()
                print("Transaction safely canceled in MDB handler.")
            except Exception as e:
                print(f"Error during transaction cancellation: {e}")

        # Close the popup
        self.after(0, self.payment_popup_frame.hide)

        # Signal the payment thread to stop (if running in a thread)
        self.payment_canceled = True
        print("Payment process marked as canceled.")



    def check_reader_status_and_reinitialize(self):
        """
        Sends a status command to the reader, checks for 'RESET' in the response,
        and reinitializes the reader if necessary. Runs in a separate thread.
        """
        def status_thread():
            try:
                print("Checking reader status...")
                self.mdb_handler.write2Serial("D,STATUS")  # Send the status command
                response = self.mdb_handler.readNWait()

                if "RESET" in response:
                    print("Reader reset detected. Attempting reinitialization...")
                    try:
                        self.mdb_handler.initserial()
                        self.mdb_handler.init_devices()
                        print("Reader reinitialized successfully.")
                    except Exception as e:
                        print(f"Failed to reinitialize the reader: {e}")
                        #messagebox.showerror("Reader Error", "Failed to reinitialize the card reader.")
                else:
                    print("Reader status is normal or no reset detected.")

            except Exception as e:
                print(f"Error while checking reader status: {e}")
            finally:
                print("Status check thread finished.")

        # Start the thread to run the status check
        thread = threading.Thread(target=status_thread, daemon=True)
        thread.start()




    def unlock_locker(self, locker_id):
        send_command(f"UNLOCK:{locker_id}")
        if self.spi_enabled:
            self.spi_handler.open_locker(locker_id)  # Example SPI command
        else:
            print("SPI is disabled, skipping SPI commands.")

    def on_button_press(self, event):
        locker_id = int(event.widget["text"])
        # Schedule the long press action after 2000 milliseconds (2 seconds)
        event.widget.long_press_timer = self.after(2000, lambda: self.prompt_admin_options(locker_id))

    def on_button_release(self, event):
        # Cancel the scheduled long press action if the button is released before 2 seconds
        if hasattr(event.widget, 'long_press_timer'):
            self.after_cancel(event.widget.long_press_timer)
            del event.widget.long_press_timer

    def prompt_admin_options(self, locker_id):
        self.selected_locker = locker_id  # Store the selected locker
        self.check_reader_status_and_reinitialize()
        self.pin_entry_frame.show()

    def on_pin_success(self, pin):
        print(f"Entered PIN: {pin}")  # Debugging statement
        if self.verify_pin(pin):
            self.pin_entry_frame.hide()
            self.show_admin_options()
        else:
            #messagebox.showerror("Invalid PIN", "The PIN you entered is incorrect.")
            self.pin_entry_frame.hide()


    def verify_pin(self, pin):
        # Replace this with your actual PIN verification logic
        correct_pin = "4671"
        return pin == correct_pin


    def show_frame(self, frame):
        """Hide all frames and show the specified frame."""
        frames = [
            self.pin_entry_frame,
            self.admin_options_frame,
            self.price_entry_frame,
            self.rgb_entry_frame,
            self.payment_popup_frame,
            self.information_frame
        ]
        for f in frames:
            f.hide()
        frame.show()
        

    def show_admin_options(self):
        """Show admin options for the selected locker."""
        locker_id = self.selected_locker
        print(f"Showing admin options for Locker ID: {locker_id}")  # Debugging
        if locker_id is not None:
            # Update admin_options_frame with the selected locker
            #self.admin_options_frame.locker_id = locker_id
            self.admin_options_frame.buttons = self.buttons  # Pass the locker buttons
            self.admin_options_frame.show(locker_id)
        else:
            print("No locker selected to show admin options.")
            print("Error", "No locker selected.")

    def change_price_callback(self):
            """Callback for changing the price of a selected locker."""
            locker_id = self.selected_locker
            if locker_id is not None:
                # Open the price entry frame
                self.price_entry_frame.locker_id = locker_id
                self.price_entry_frame.show(locker_id)
            else:
                print("No Locker Selected", "Please select a locker to change its price.")



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

        #messagebox.showinfo("Price Updated", f"Price for Locker {locker_id} set to {new_price:.2f}€")



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



    def transfer_rgb_to_stm32(self):
        """
        Transfer RGB color information from JSON to STM32 via SPI.
        """
        if self.spi_enabled:
            for locker_id, data in self.locker_data.items():
                red = data.get("red", 0)
                green = data.get("green", 0)
                blue = data.get("blue", 0)
                locker_number = int(locker_id)
                self.spi_handler.set_led_color(locker_number, red, green, blue)
                print(f"LED color for Locker {locker_number} set to RGB({red}, {green}, {blue})")
                time.sleep(0.05)
        else:
            print("SPI is disabled, skipping RGB transfer.")



    def keyboard_listener(self, event):
        if event.keysym == 'Escape':
            self.quit()


    def start_move(self, event):
        """Capture the initial position when dragging starts."""
        self._offsetx = event.x
        self._offsety = event.y

    def stop_move(self, event):
        """Reset the offsets when dragging stops."""
        self._offsetx = 0
        self._offsety = 0

    def do_move(self, event):
        """Calculate the new position of the window during dragging."""
        x = self.winfo_pointerx() - self._offsetx
        y = self.winfo_pointery() - self._offsety
        self.geometry(f"+{x}+{y}")


    def on_close(self):
        """Perform cleanup and exit the application."""
        # Stop the scheduler
        if self.scheduler:
            self.scheduler.stop()
            print("Scheduler stopped.")

        # Close the SPI handler
        if hasattr(self, 'spi_handler') and self.spi_handler:
            try:
                self.spi_handler.close()
            except Exception as e:
                print(f"Error during SPIHandler cleanup: {e}")

        # Check if MDB handler exists before calling its cleanup
        if hasattr(self, 'mdb_handler') and self.mdb_handler:
            try:
                print("Ending communication with MDB reader...")
                self.mdb_handler.end_comunication()
            except Exception as e:
                print(f"Error during MDBHandler cleanup: {e}")

        # Destroy the application window
        self.bot_queue.put(None)  # Tells the bot to stop
        self.destroy()

