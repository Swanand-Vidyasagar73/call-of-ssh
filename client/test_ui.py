from ui import run_ui
import time

def fake_send(text):
    ui.add_message("you", text)

ui = run_ui(fake_send)

while True:
    time.sleep(1)