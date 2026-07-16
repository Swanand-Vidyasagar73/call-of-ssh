import curses
import threading
import time


class ChatUI:
    def __init__(self, stdscr, on_send):
        self.stdscr = stdscr
        self.on_send = on_send   # callback: called with the typed text
        self.messages = []
        self.lock = threading.Lock()

        curses.curs_set(1)
        self.height, self.width = stdscr.getmaxyx()
        self.msg_win = curses.newwin(self.height - 3, self.width, 0, 0)
        self.input_win = curses.newwin(3, self.width, self.height - 3, 0)
        self.msg_win.scrollok(True)

    def add_message(self, sender, content):
        with self.lock:
            self.messages.append(f"{sender}: {content}")
            self.redraw_messages()

    def redraw_messages(self):
        self.msg_win.clear()
        visible = self.messages[-(self.height - 4):]
        for i, line in enumerate(visible):
            self.msg_win.addstr(i, 0, line[:self.width - 1])
        self.msg_win.refresh()

    def input_loop(self):
        curses.echo()
        while True:
            self.input_win.clear()
            self.input_win.border()
            self.input_win.addstr(1, 1, "> ")
            self.input_win.refresh()
            text = self.input_win.getstr(1, 3).decode("utf-8")
            if text.strip():
                self.on_send(text)


def run_ui(on_send):
    """Returns the ChatUI instance so a networking thread can push
    incoming messages into it via add_message()."""
    holder = {}

    def _main(stdscr):
        ui = ChatUI(stdscr, on_send)
        holder["ui"] = ui
        ui.input_loop()   # blocks, runs forever

    threading.Thread(target=lambda: curses.wrapper(_main), daemon=True).start()
    while "ui" not in holder:
        time.sleep(0.05)
    return holder["ui"]