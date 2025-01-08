# app.py
import tkinter as tk
from tkinter import messagebox, TclError
import time
import os
from admin_windows import PinEntryWindow, AdminOptionsWindow, PriceEntryWindow, RGBEntryWindow, PaymentPopup
from utils import load_locker_data, save_locker_data, send_command, log_event
from spi_handler import SPIHandler
from scheduler import Scheduler
from mdb_handler import MDBHandler
import threading
import time

class VendingMachineApp(tk.Tk):
    def __init__(self, bot_queue):
        super().__init__()
        self.bot_queue = bot_queue
        self.title("Vending Machine")
        self.geometry("800x480")
        self.configure(bg="#C3C3C3")
        self.selected_locker = None
        self.locker_data = load_locker_data()

        # Initialize the scheduler
        self.scheduler = Scheduler()
        self.scheduler.start()

        # Boolean to enable or disable PIN check on exit
        self.require_exit_pin = False  # Set to False to disable PIN verification on exit

        # Load images (assuming they're in an 'img' folder)
        self.pay_image = tk.PhotoImage(file=os.path.join("img", "icon3.png"))

        # Load button images
        self.button_images = [tk.PhotoImage(file=os.path.join("img", f"button{i}.png")) for i in range(1, 13)]


        

        
        # SPIHandler initialization with error handling
        try:
            self.spi_handler = SPIHandler(bus=0, device=0, speed_hz=500000)
            self.spi_enabled = True
            print("SPI initialized successfully.")
            self.transfer_rgb_to_stm32()
            self.transfer_prices_to_stm32()
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
            messagebox.showerror("Error", f"MDB Initialization Failed: {e}")
            self.mdb_handler = None


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
        """Process payment when the PAY button is clicked."""
        if self.selected_locker is None:
            messagebox.showwarning("No Selection", "Please select a locker before paying.")
            return

        locker_id = self.selected_locker
        price = self.locker_data[str(locker_id)]["price"]
        product_code = locker_id  # Use locker_id as the product code for vending.
        self.payment_success = False
        self.payment_canceled = False

        # Step 1: Create the popup in the main thread
        self.popup = PaymentPopup(self, cancel_callback=self.cancel_transaction)

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
                    messagebox.showerror("Reader Disconnected", "Card reader is disconnected or unresponsive.")
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
                            messagebox.showinfo("Payment Canceled", "Payment was canceled by the customer.")
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
                else:
                    raise ValueError("Payment verification failed. Locker will not be unlocked.")

            except (ConnectionError, TimeoutError, ValueError) as e:
                print(f"Payment Error: {e}")
                messagebox.showerror("Payment Failed", str(e))

            except Exception as e:
                print(f"Unexpected Error: {e}")
                messagebox.showerror("Error", f"An unexpected error occurred: {e}")

            finally:
                # Ensure the popup is closed
                if hasattr(self, 'popup') and self.popup:
                    self.popup.destroy()
                    del self.popup
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
        if hasattr(self, 'popup') and self.popup:
            self.popup.destroy()
            del self.popup

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
                        messagebox.showerror("Reader Error", "Failed to reinitialize the card reader.")
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
        self.press_time = time.time()

    def on_button_release(self, event):
        hold_duration = time.time() - self.press_time
        if hold_duration >= 2:
            locker_id = int(event.widget["text"])
            self.prompt_admin_options(locker_id)

    def prompt_admin_options(self, locker_id):
        self.check_reader_status_and_reinitialize()
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
            unlock_callback=self.unlock_locker,
            price_callback=self.change_price_callback,
            locker_data=self.locker_data,
            buttons=self.buttons,
            save_callback=save_locker_data,  # Pass the save function as a callback
            spi_handler=self.spi_handler,
            close_program_callback = self.on_close
        )


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
        self.destroy()

