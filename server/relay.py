import socket
import threading

HOST = "0.0.0.0"
PORT = 9999

# in-memory only — never written to disk, wiped on restart
connected_peers = {}
lock = threading.Lock()


def handle_client(conn, addr):
    buf = b""
    username = None
    try:
        # --- handshake: first line must be "<username>\n" ---
        while username is None:
            chunk = conn.recv(4096)
            if not chunk:
                conn.close()
                return  # disconnected before handshake
            buf += chunk
            if b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                username = line.decode().strip()
                with lock:
                    if username in connected_peers:
                        conn.sendall(b"ERROR|username-taken\n")
                        conn.close()
                        return
                    connected_peers[username] = conn
                print(f"[relay] {username} connected from {addr}")

        # --- message loop: one "target|json" line at a time ---
        while True:
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    return  # client disconnected (cleanup in finally)
                buf += chunk
            line, buf = buf.split(b"\n", 1)
            if not line.strip():
                continue
            # wire format per line: "target_username|<json_payload>"
            target, _, payload = line.partition(b"|")
            target = target.decode().strip()
            if not target or not payload:
                continue  # malformed line, ignore
            with lock:
                target_conn = connected_peers.get(target)
            if target_conn:
                try:
                    target_conn.sendall(payload + b"\n")
                except OSError:
                    pass  # target died mid-send; drop (offline queue = future work)
            else:
                # target offline — tell sender instead of dropping silently
                try:
                    conn.sendall(b"ERROR|user-offline\n")
                except OSError:
                    pass
    finally:
        if username:
            with lock:
                # only remove if it's still our conn (don't kick a newer login)
                if connected_peers.get(username) is conn:
                    connected_peers.pop(username, None)
            print(f"[relay] {username} disconnected")
        else:
            print(f"[relay] connection from {addr} closed before handshake")
        try:
            conn.close()
        except OSError:
            pass
    
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