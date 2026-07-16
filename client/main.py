import sys
import time
import getpass
from ssh_client import connect, open_shell_channel
from message import make_message, parse_message
from ui import run_ui
from storage import EncryptedFlatStore

if len(sys.argv) != 2 or sys.argv[1] not in ("alice", "bob"):
    print("Usage: python main.py [alice|bob]")
    sys.exit(1)

USERNAME = sys.argv[1]
KEY_PATH = f"keys/{USERNAME}_id_ed25519"
HOST = "127.0.0.1"
PORT = 2222
SSH_LOGIN_USER = "swanand"


def main():
    passphrase = getpass.getpass("Enter storage passphrase: ")
    store = EncryptedFlatStore(f"data/{USERNAME}_chat.dat", passphrase)

    client = connect(HOST, PORT, SSH_LOGIN_USER, KEY_PATH)
    channel = open_shell_channel(client)

    def on_send(text):
        channel.send(make_message(USERNAME, text))
        store.append(USERNAME, time.time(), text)
        ui.add_message(USERNAME, text)

    ui = run_ui(on_send)

    for m in store.messages:
        ui.add_message(m["sender"], m["content"])

    buffer = ""
    while True:
        if channel.recv_ready():
            buffer += channel.recv(4096).decode("utf-8", errors="ignore")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line.strip():
                    try:
                        sender, ts, content = parse_message(line)
                        ui.add_message(sender, content)
                        if sender != USERNAME:
                            store.append(sender, ts, content)
                    except Exception:
                        pass  


if __name__ == "__main__":
    main()