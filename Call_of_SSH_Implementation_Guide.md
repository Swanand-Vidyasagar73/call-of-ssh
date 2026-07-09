# Call of SSH — In-Depth Implementation Guide (Windows Edition)

This guide is written for **Windows**, with two tracks throughout:

- **Track A: WSL (recommended)** — you run everything inside WSL (Windows Subsystem for Linux), which behaves exactly like a real Linux box. Every command is standard Linux, nothing to substitute.
- **Track B: Native Windows** — no WSL, running Python directly on Windows. A few tools need swapping (noted at each step).

If you don't already have WSL, set it up now — it's one command and saves you from fighting Windows-specific quirks for the rest of the project:

```powershell
wsl --install
```

Restart when prompted, then open the "Ubuntu" app from your Start menu. Everything under "Track A" below runs inside that Ubuntu window.

Tech stack (minimal, cross-platform where possible):

| Piece | Tool | Install |
|---|---|---|
| Language | Python 3 | Already on WSL; on native Windows, install from python.org |
| SSH | `paramiko` | `pip install paramiko` |
| Terminal UI | `curses` (WSL) / `windows-curses` (native) | Built-in on WSL; `pip install windows-curses` on native |
| Identity | `ssh-keygen` (ed25519) | Built-in on WSL; ships with Windows OpenSSH client too |
| Storage encryption | `cryptography` (AES-GCM) | `pip install cryptography` |
| Message format | `json` | Built-in |
| Relay | `socket` | Built-in |

Project structure (create this now):

```
call-of-ssh/
├── client/
│   ├── ssh_client.py
│   ├── ui.py
│   ├── storage.py
│   └── message.py
├── server/
│   └── relay.py
├── keys/              # generated keypairs live here, gitignored
├── data/              # per-user encrypted files, gitignored
└── requirements.txt
```

**Track A (WSL):**
```bash
mkdir -p call-of-ssh/{client,server,keys,data}
cd call-of-ssh
python3 -m venv venv
source venv/bin/activate
pip install paramiko cryptography
echo "paramiko
cryptography" > requirements.txt
```

**Track B (native Windows, PowerShell):**
```powershell
mkdir call-of-ssh\client, call-of-ssh\server, call-of-ssh\keys, call-of-ssh\data
cd call-of-ssh
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install paramiko cryptography windows-curses
"paramiko`ncryptography`nwindows-curses" | Out-File requirements.txt
```

Everything below has no other track-specific changes unless explicitly called out — Python code is identical either way.

---

## Phase 1: SSH transport basics

**Goal:** prove you can send bytes over an authenticated SSH session between two machines (or two terminals on the same machine — that's fine for dev).

### Step 1.1 — Get an SSH server running

**Track A (WSL):**
```bash
sudo apt install openssh-server
sudo service ssh start
sudo service ssh status   # confirm "running"
```

**Track B (native Windows):**
Settings → Apps → Optional Features → "Add a feature" → search "OpenSSH Server" → Install.
Then start it as a service:
```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'   # optional: auto-start on boot
```
Config file lives at `C:\ProgramData\ssh\sshd_config` (instead of `/etc/ssh/sshd_config`).

### Step 1.2 — Run it on a dedicated test port with its own keys

This keeps your project's SSH server separate from your normal login setup so you don't touch real system config.

**Track A (WSL):**
```bash
mkdir -p ~/call-of-ssh-test/etc
cat > ~/call-of-ssh-test/etc/sshd_config << 'EOF'
Port 2222
ListenAddress 127.0.0.1
HostKey /home/YOUR_USER/call-of-ssh-test/etc/ssh_host_ed25519_key
PubkeyAuthentication yes
PasswordAuthentication no
AuthorizedKeysFile /home/YOUR_USER/call-of-ssh/keys/authorized_keys
EOF
ssh-keygen -t ed25519 -f ~/call-of-ssh-test/etc/ssh_host_ed25519_key -N ""
sudo /usr/sbin/sshd -f ~/call-of-ssh-test/etc/sshd_config -D
```
`-D` keeps it in the foreground so you can see logs and Ctrl+C it. Replace `YOUR_USER` with your actual username.

**Track B (native Windows):**
Native Windows OpenSSH doesn't easily support a second custom-port instance without editing the main service config. Simplest path: edit `C:\ProgramData\ssh\sshd_config` directly, add a line `Port 2222`, and point `AuthorizedKeysFile` at your project's `keys\authorized_keys` (use forward slashes or escaped backslashes). Then restart the service: `Restart-Service sshd`. Since this touches the shared system config, remember to revert it once your project is done.

*(If this feels fiddly, this is the single strongest argument for Track A — WSL sidesteps all of this.)*

### Step 1.3 — Connect with paramiko and send raw bytes

`client/ssh_client.py`:

```python
import paramiko

def connect(host, port, username, key_path):
    key = paramiko.Ed25519Key.from_private_key_file(key_path)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=username, pkey=key)
    return client

def open_shell_channel(client):
    channel = client.invoke_shell()
    return channel

if __name__ == "__main__":
    client = connect("127.0.0.1", 2222, "YOUR_USER", "keys/alice_id_ed25519")
    chan = open_shell_channel(client)

    chan.send("echo hello-over-ssh\n")
    import time
    time.sleep(1)
    print(chan.recv(4096).decode())

    client.close()
```

You need a keypair before this runs — that's Phase 2, do it next, then come back.

### Checkpoint

Running `python client/ssh_client.py` (or `python3 ...` on WSL) prints back the echoed text from the remote shell. If you get `Authentication failed`, your public key isn't registered yet — Phase 2 fixes that.

---

## Phase 2: Key-based identity

**Goal:** every user has an ed25519 keypair; login only works with a registered public key; you can map a key fingerprint to a display username.

### Step 2.1 — Generate keypairs per user

Same command on both tracks (Windows OpenSSH client ships `ssh-keygen` too):

```bash
ssh-keygen -t ed25519 -f keys/alice_id_ed25519 -C "alice" -N ""
ssh-keygen -t ed25519 -f keys/bob_id_ed25519 -C "bob" -N ""
```

On native Windows PowerShell, this is the exact same command — `ssh-keygen.exe` is on PATH once the OpenSSH client feature is installed (Settings → Optional Features → "OpenSSH Client", usually on by default).

### Step 2.2 — Register public keys

```bash
cat keys/alice_id_ed25519.pub >> keys/authorized_keys
cat keys/bob_id_ed25519.pub >> keys/authorized_keys
```

PowerShell equivalent:
```powershell
Get-Content keys\alice_id_ed25519.pub | Add-Content keys\authorized_keys
Get-Content keys\bob_id_ed25519.pub | Add-Content keys\authorized_keys
```

### Step 2.3 — Fingerprint-to-username mapping

`client/identity.py` (identical on both tracks, pure Python):

```python
import hashlib
import base64
import json

USER_REGISTRY_PATH = "keys/user_registry.json"

def fingerprint_from_pubkey_file(pub_path):
    with open(pub_path) as f:
        parts = f.read().strip().split()
    key_type, b64_key = parts[0], parts[1]
    raw = base64.b64decode(b64_key)
    digest = hashlib.sha256(raw).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")

def register_user(username, pub_path):
    fp = fingerprint_from_pubkey_file(pub_path)
    try:
        with open(USER_REGISTRY_PATH) as f:
            registry = json.load(f)
    except FileNotFoundError:
        registry = {}
    registry[fp] = username
    with open(USER_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    return fp

def lookup_username(fingerprint):
    with open(USER_REGISTRY_PATH) as f:
        registry = json.load(f)
    return registry.get(fingerprint, "unknown")

if __name__ == "__main__":
    fp = register_user("alice", "keys/alice_id_ed25519.pub")
    print(f"Registered alice as {fp}")
    print(lookup_username(fp))
```

This is what your architecture doc means by "identity is a key pair, not a phone number" — the fingerprint IS the identity; the registry file is just a friendly-name lookup, not an authority.

### Checkpoint

`python client/identity.py` prints a `SHA256:...` fingerprint and resolves it back to `alice`. Cross-check with `ssh-keygen -lf keys/alice_id_ed25519.pub` — the underlying hash should match (format differs slightly, same idea).

---

## Phase 3: Message framing and CLI

**Goal:** define a message format, build a scrollable curses UI with an input line, send/receive JSON-lines over the SSH channel from Phase 1.

### Step 3.1 — Message format

`client/message.py` (identical both tracks):

```python
import json
import time

def make_message(sender, content):
    return json.dumps({
        "sender": sender,
        "timestamp": time.time(),
        "content": content
    }) + "\n"   # newline-delimited = "JSON-lines"

def parse_message(line):
    data = json.loads(line)
    return data["sender"], data["timestamp"], data["content"]
```

### Step 3.2 — Curses TUI: scrollable pane + input line

`client/ui.py` — **this code is identical on both tracks.** On native Windows, `pip install windows-curses` (already in your requirements.txt above) makes the standard `import curses` work exactly the same as on Linux — no code changes needed, just that one extra package.

```python
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
```

### Step 3.3 — Wire it together

`client/main.py`:

```python
from ssh_client import connect, open_shell_channel
from message import make_message, parse_message
from ui import run_ui

USERNAME = "alice"

def main():
    client = connect("127.0.0.1", 2222, USERNAME, "keys/alice_id_ed25519")
    channel = open_shell_channel(client)

    def on_send(text):
        channel.send(make_message(USERNAME, text))

    ui = run_ui(on_send)

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
                    except Exception:
                        pass  # not a JSON message line, ignore

if __name__ == "__main__":
    main()
```

### Checkpoint

Run two instances (one per user). Typing in the input line and hitting Enter should show `alice: your text` scroll into the message pane above. On native Windows, run this from a real terminal (Windows Terminal or PowerShell) — the old `cmd.exe` box handles curses redraws poorly.

---

## Phase 4: Local encrypted storage

**Goal:** persist every message locally, encrypted at rest, unreadable without the key. Using AES-GCM here — pure Python, no native library install, identical on both tracks.

`client/storage.py`:

```python
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def derive_key(passphrase, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    return kdf.derive(passphrase.encode())

class EncryptedFlatStore:
    def __init__(self, path, passphrase):
        self.path = path
        if os.path.exists(path):
            with open(path, "rb") as f:
                raw = f.read()
            self.salt, nonce, ciphertext = raw[:16], raw[16:28], raw[28:]
            key = derive_key(passphrase, self.salt)
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
            self.messages = json.loads(plaintext)
        else:
            self.salt = os.urandom(16)
            self.messages = []
        self.key = derive_key(passphrase, self.salt)

    def save_all(self):
        nonce = os.urandom(12)
        plaintext = json.dumps(self.messages).encode()
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, None)
        with open(self.path, "wb") as f:
            f.write(self.salt + nonce + ciphertext)

    def append(self, sender, timestamp, content):
        self.messages.append({"sender": sender, "timestamp": timestamp, "content": content})
        self.save_all()
```

Usage:

```python
import getpass
passphrase = getpass.getpass("Enter storage passphrase: ")
store = EncryptedFlatStore("data/alice_chat.dat", passphrase)
store.append("alice", 1234567890.0, "hello")
```

Note: `getpass` works fine in a normal Windows terminal (PowerShell, Windows Terminal, WSL) — it just won't show the typed characters, same as Linux.

### Checkpoint

Delete/rename the file, or try opening it with the wrong passphrase — it should raise an `InvalidTag` exception, not silently return garbage. That failure *is* the proof it's actually encrypted, not just obscured. Also run, from a terminal:

**WSL:** `strings data/alice_chat.dat | grep -i "hello"`
**Native Windows (PowerShell):** `Select-String -Path data\alice_chat.dat -Pattern "hello"`

Both should return nothing — if your message content shows up in plaintext, something's wrong before you write this up as a strength.

---

## Phase 5: Stateless relay (optional, for NAT traversal)

**Goal:** a minimal server that forwards encrypted bytes between two connected clients, never writing message content to disk. Pure `socket`, identical code on both tracks.

`server/relay.py`:

```python
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
            # true statelessness means no offline queue unless you explicitly add one
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
```

Key design point for your threat-model writeup: `payload` is bytes the relay never inspects or parses — already encrypted client-side. The relay only routes. Seize this server, you get an empty in-memory dict and zero history.

### Checkpoint

Start the relay, connect two test clients, send a message from one, confirm the other receives it, then kill the relay process and confirm `connected_peers` — and all message content — is gone.

---

## Phase 6: Testing and threat model writeup

**Goal:** validate reliability under real conditions, prove storage is unreadable without the key, document resistance to the threat model.

### Step 6.1 — Latency/dropout testing

**Track A (WSL):** WSL's networking is virtualized through Windows, so Linux's `tc netem` doesn't reliably apply the way it would on bare-metal Linux. Skip `tc` and instead simulate delay/loss directly in your Python code for testing purposes:

```python
import random
import time

def flaky_send(channel, data, loss_rate=0.05, max_delay=0.2):
    if random.random() < loss_rate:
        return  # simulate dropped packet
    time.sleep(random.uniform(0, max_delay))  # simulate latency
    channel.send(data)
```

Swap `channel.send(...)` for `flaky_send(channel, ...)` temporarily in your client to stress-test message reassembly.

**Track B (native Windows):** use **Clumsy** (a small free GUI tool for simulating latency/packet loss on Windows network adapters) if you want an OS-level simulation instead of the Python-level one above.

Either way, confirm your JSON-lines buffer in Phase 3 correctly reassembles a message that arrives split across two `recv()` calls — the `buffer +=` accumulation pattern already handles this, but verify under simulated loss.

### Step 6.2 — Storage unreadability test

Script that:
1. Opens your encrypted store with the correct passphrase → succeeds, prints messages.
2. Opens it with a wrong passphrase → must raise `InvalidTag`, not silently return garbage.
3. Searches the raw file for your test message content (commands above in Phase 4's checkpoint) — should find nothing.

### Step 6.3 — Threat model writeup structure

Use the comparison table from your problem statement as the backbone; for each row, write 2-3 sentences on *how your implementation specifically achieves it*, citing the actual mechanism:

- **Transport**: SSH's authenticated key exchange (Phase 1/2) vs. proprietary TLS stacks that aren't independently auditable.
- **Message storage**: your Step 6.2 test as empirical proof, not just a design claim.
- **Identity**: the fingerprint mechanism from Phase 2, contrasted with SIM-swap attack surface.
- **Server trust**: the relay's in-memory-only design from Phase 5, with "kill the process, data is gone" as evidence.
- **Auditability**: your entire codebase is inspectable, unlike closed-source vendor apps.

Be honest about limits too: a stateless relay with no offline queue means messages sent while a peer is offline are simply lost — a real tradeoff versus WhatsApp/Signal's server-side queueing, and closing that gap is legitimate future work.

---

## Quick reference: priority order if short on time

**Phase 1 → Phase 2 → Phase 3 → Phase 4.** Phase 5 (relay) and the network-simulation part of Phase 6 are the first things worth trimming — a direct two-terminal demo with encrypted local storage already proves your core thesis.

## Track A vs Track B — one-line summary

If you haven't started yet: **use WSL (Track A).** Every command in this guide runs unmodified, matches how real-world SSH/Linux tooling actually works, and avoids the handful of Windows-native workarounds (service config editing, Clumsy instead of `tc`, terminal-choice sensitivity for curses) called out above.
