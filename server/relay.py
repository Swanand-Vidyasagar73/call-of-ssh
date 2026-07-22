import socket
import threading

HOST = "0.0.0.0"
PORT = 9999

# in-memory only — never written to disk, wiped on restart
connected_peers = {}
lock = threading.Lock()


def handle_client(conn, addr):
    username = conn.recv(1024).decode().strip()  # client sends its username first
    with lock:
        connected_peers[username] = conn
    print(f"[relay] {username} connected from {addr}")

    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            # wire format from client: "target_username|<encrypted_payload_bytes>"
            target, _, payload = data.partition(b"|")
            target = target.decode()
            with lock:
                target_conn = connected_peers.get(target)
            if target_conn:
                target_conn.sendall(payload)
            # if target isn't online right now, payload is dropped —
            # true statelessness means no offline queue unless explicitly added
    finally:
        with lock:
            connected_peers.pop(username, None)
        conn.close()
        print(f"[relay] {username} disconnected")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[relay] listening on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()