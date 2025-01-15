#gui.py
import tkinter as tk
import os

BG_COLOR = "#8bcbb9"
GREEN_COLOR = "#1e6039"
TAG_COLOR = "#b92387"

def size(self):
    self.title("Vending Machine")
    self.geometry("1920x1200")
    self.configure(bg="#8bcbb9")

def load_images(self):
    # Load images (assuming they're in an 'img' folder)
    self.pay_image = tk.PhotoImage(file=os.path.join("new", "pay.png"))
    # Load button images
    self.button_images = [tk.PhotoImage(file=os.path.join("new", f"button{i}.png")) for i in range(1, 15)]


def create_locker_buttons(self):
    button_specs = [
        {"size": (400, 400), "pos": (185, 55)},
        {"size": (170, 170), "pos": (645, 55)},
        {"size": (170, 170), "pos": (875, 55)},
        {"size": (170, 170), "pos": (1105, 55)},
        {"size": (400, 400), "pos": (1335, 55)},
        {"size": (170, 170), "pos": (645, 285)},
        {"size": (170, 170), "pos": (1105, 285)},
        {"size": (400, 400), "pos": (185, 515)},
        {"size": (170, 170), "pos": (645, 515)},
        {"size": (170, 170), "pos": (1105, 515)},
        {"size": (400, 400), "pos": (1335, 515)},
        {"size": (170, 170), "pos": (645, 745)},
        {"size": (170, 170), "pos": (875, 745)},       
        {"size": (170, 170), "pos": (1105, 745)}
    ]

    self.buttons = {}
    for i, spec in enumerate(button_specs, start=1):
        locker_id = str(i)
        status = self.locker_data[locker_id]["status"]
        button = tk.Button(self, image=self.button_images[i-1], text=str(i), font=("Arial", 18, "bold"), bg="#8bcbb9", activebackground="#8bcbb9", state="disabled" if not status else "normal", borderwidth=0, fg="black", highlightthickness=0)
        button.place(x=spec["pos"][0], y=spec["pos"][1], width=spec["size"][0], height=spec["size"][1])
        button.bind("<ButtonPress-1>", self.on_button_press)
        button.bind("<ButtonRelease-1>", self.on_button_release)
        self.buttons[i] = button

def create_pay_button(self):
    self.pay_button = tk.Button(self, image=self.pay_image, command=self.process_payment, borderwidth=0, bg="#8bcbb9", activebackground="#8bcbb9", highlightthickness=0)
    self.pay_button.place(x=195, y=985, width=1530, height=150)

def create_close_button(app):
    """Create a custom close button."""
    close_button = tk.Button(
        app,
        text="X",
        command=app.on_close,
        bg="#FF0000",
        fg="#FFFFFF",
        borderwidth=0,
        font=("Arial", 12, "bold"),
        activebackground="#CC0000",
        highlightthickness=0
    )
    close_button.place(x=1850, y=5, width=30, height=30)  # Adjust position based on window size


def create_title_bar(app):
    """Create a custom title bar for dragging and housing window controls."""
    title_bar = tk.Frame(app, bg="#2e2e2e", relief='raised', bd=0)
    title_bar.place(x=0, y=0, width=1920, height=40)  # Adjust height as needed

    # Bind dragging to the title bar only
    title_bar.bind("<ButtonPress-1>", app.start_move)
    title_bar.bind("<ButtonRelease-1>", app.stop_move)
    title_bar.bind("<B1-Motion>", app.do_move)

    # Add a title label
    title_label = tk.Label(title_bar, text="Vending Machine", bg="#2e2e2e", fg="#FFFFFF", font=("Arial", 14, "bold"))
    title_label.pack(side='left', padx=10)
    
    # Make the title label draggable as well
    title_label.bind("<ButtonPress-1>", app.start_move)
    title_label.bind("<ButtonRelease-1>", app.stop_move)
    title_label.bind("<B1-Motion>", app.do_move)
