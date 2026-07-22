import sys
import time
import socket
import threading
import getpass

from message import make_message, parse_message
from ui import run_ui
from storage import EncryptedFlatStore

if len(sys.argv) < 2 or sys.argv[1] not in ("alice", "bob"):
    print("Usage: python main.py [alice|bob]")
    sys.exit(1)

USERNAME = sys.argv[1]
RELAY_HOST = "127.0.0.1"   # replace with the relay server's public IP if hosting for friends
RELAY_PORT = 9999


def main():
    target = input("Who do you want to chat with? (target username): ").strip()

    passphrase = getpass.getpass("Enter storage passphrase: ")
    store = EncryptedFlatStore(f"data/{USERNAME}_chat.dat", passphrase)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((RELAY_HOST, RELAY_PORT))
    sock.sendall(USERNAME.encode())   # handshake: register this username with the relay

    def on_send(text):
        payload = make_message(USERNAME, text).encode()
        sock.sendall(target.encode() + b"|" + payload)
        store.append(USERNAME, time.time(), text)
        ui.add_message(USERNAME, text)

    ui = run_ui(on_send)

    # replay any previously stored history into the UI on startup
    for m in store.messages:
        ui.add_message(m["sender"], m["content"])

    def receive_loop():
        buffer = ""
        while True:
            try:
                data = sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            buffer += data.decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line.strip():
                    try:
                        sender, ts, content = parse_message(line)
                        ui.add_message(sender, content)
                        if sender != USERNAME:
                            store.append(sender, ts, content)
                    except Exception:
                        pass  # not a JSON message line, ignore

    threading.Thread(target=receive_loop, daemon=True).start()

    while True:
        time.sleep(0.5)   # keep main thread alive; UI + receive_loop run in background threads


if __name__ == "__main__":
    main()