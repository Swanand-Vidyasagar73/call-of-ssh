# Call of SSH — Windows Setup & Run Guide

Complete guide for setting up and running Call of SSH on native Windows (no WSL needed), using the repo: `https://github.com/Swanand-Vidyasagar73/call-of-ssh`

> Companion to `Call_of_SSH_Arch_Linux_Guide.md`. The code is identical on both platforms — only setup commands and test tools differ.

---

## Part 1: Prerequisites (one-time)

### Step 1.1 — Install Python

1. Download Python 3.11+ from **https://www.python.org/downloads/**
2. During install, tick **"Add python.exe to PATH"**
3. Verify in PowerShell:
   ```powershell
   python --version
   ```

Avoid the Microsoft Store Python build — it causes PATH and permission headaches. `python.org` builds just work.

### Step 1.2 — Install a good terminal

Use **Windows Terminal** (free, from the Microsoft Store) or plain PowerShell. The old `cmd.exe` box renders the `curses` chat UI poorly (flicker, broken borders).

### Step 1.3 — Check for `ssh-keygen` and `git`

```powershell
ssh-keygen
git --version
```

* `ssh-keygen` ships with the **OpenSSH Client** (preinstalled on Windows 10/11). If missing: Settings → Apps → Optional Features → Add a feature → **OpenSSH Client**.
* If `git` is missing: install from **https://git-scm.com/download/win** (accept all defaults).

What each one does:

| Tool | Purpose |
|---|---|
| `python` | runs the app |
| `pip` (bundled) | installs paramiko/cryptography/windows-curses inside a venv |
| `ssh-keygen` | generates the ed25519 identity keypairs |
| `git` | clone and manage your repo |
| Windows Terminal | renders the `curses` chat UI correctly |

Note: you do **NOT** need an SSH server (`sshd`) — the chat talks to the relay server over plain sockets, not SSH. `ssh-keygen` is only used to create identity keys.

---

## Part 2: Clone the repo and set up the environment

### Step 2.1 — Clone

```powershell
git clone https://github.com/Swanand-Vidyasagar73/call-of-ssh.git
cd call-of-ssh
```

### Step 2.2 — Create a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

You'll know it's active when your prompt shows `(venv)` at the start.

If activation is blocked with an execution-policy error, run this once per PowerShell window and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Step 2.3 — Install dependencies

```powershell
pip install -r requirements.txt
```

`requirements.txt` contains:

```
paramiko==5.0.0
cryptography==49.0.0
windows-curses==2.4.2; sys_platform == "win32"
```

The third line installs `windows-curses` **only on Windows** (the `sys_platform` marker) — Linux/macOS installs skip it automatically, and no code changes are needed either way: `import curses` just works once the package is present.

Verify:

```powershell
pip freeze | Select-String -Pattern "paramiko|cryptography|windows-curses"
```

You should see all three packages listed.

---

## Part 3: Generate keys and register users

Your `.gitignore` excludes `keys/` and `data/` — private keys and encrypted chat data shouldn't live in git — so you regenerate these fresh on every machine.

### Step 3.1 — Generate ed25519 keypairs

```powershell
mkdir keys, data
ssh-keygen -t ed25519 -f keys\alice_id_ed25519 -C "alice" -N '""'
ssh-keygen -t ed25519 -f keys\bob_id_ed25519 -C "bob" -N '""'
```

Note the `-N '""'` (empty passphrase) — the quotes are required in PowerShell.

### Step 3.2 — Register public keys and fingerprints

```powershell
Get-Content keys\alice_id_ed25519.pub | Add-Content keys\authorized_keys
Get-Content keys\bob_id_ed25519.pub | Add-Content keys\authorized_keys
python client\identity.py
```

Expected output — both users registered with their `SHA256:` fingerprints:

```
Registered Alice as SHA256:...
alice
Registered Bob as SHA256:...
bob
```

### Checkpoint

```powershell
dir keys
type keys\user_registry.json
```

You should see `alice_id_ed25519`, `bob_id_ed25519` (+ `.pub` files), `authorized_keys`, and a `user_registry.json` mapping two fingerprints to `alice` and `bob`.

---

## Part 4: Run the app

Open **three PowerShell tabs**, all in the `call-of-ssh\` folder, all with the venv activated. (Always launch from the repo root — `keys/` and `data/` are relative paths and break if you `cd` into `client\` first.)

```powershell
# tab 1: relay server
python server\relay.py
```

```powershell
# tab 2: alice
python client\main.py alice
```

```powershell
# tab 3: bob
python client\main.py bob
```

Each client asks for:

1. **Target username** — type `bob` in Alice's window, `alice` in Bob's.
2. **Storage passphrase** — encrypts that user's local history file (`data\<user>_chat.dat`). Use any passphrase; remember it, since the history can't be opened without it.

Type in the `> ` input box and hit Enter — messages appear in the pane above on both ends. `Ctrl+C` exits cleanly (`Disconnected. Bye!`).

### Firewall note

Windows may pop up **"Windows Defender Firewall has blocked some features of Python"** → click **Allow**. This is only required when hosting the relay for other machines; a same-PC demo over `127.0.0.1` works regardless.

### Hosting for friends (same Wi-Fi)

1. On the host PC, find its LAN IP: `ipconfig` → `IPv4 Address` (e.g. `192.168.1.5`).
2. Start the relay on the host (it already listens on `0.0.0.0:9999`) and Allow the firewall prompt.
3. On each friend's PC, edit `client\main.py`: `RELAY_HOST = "192.168.1.5"` (host's IP).
4. Everyone runs their own client with their own username and keys.

---

## Part 5: Testing (Windows notes)

* **Storage unreadability check** (proves AES-GCM works — send a message containing "hello" first):
  ```powershell
  Select-String -Path data\alice_chat.dat -Pattern "hello"
  ```
  This should return nothing. If your message text shows up, encryption is broken.

* **Wrong-passphrase check** — open a client with a wrong storage passphrase. It must fail (an `InvalidTag`-style error), never silently show garbage. That failure *is* the proof it's encrypted.

* **Relay-blindness check** (after E2E encryption lands) — watch the relay tab while chatting: it should show only connect/disconnect lines, never message content.

* **Latency/loss simulation** — Windows has no `tc netem`. Use **Clumsy** (free GUI tool, https://jagt.github.io/clumsy/) to add lag/drops on loopback, or temporarily swap `sendall(...)` for a `flaky_send(...)` with random drops in `client\main.py`.

* **20-message framing test** — send many rapid messages; all must arrive complete and in order (validates the relay's line-buffered routing).

---

## Part 6: Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named '_curses'` | `windows-curses` not installed | venv activated? → `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'paramiko'` | venv not activated, or installed to wrong Python | `.\venv\Scripts\Activate.ps1`, then `pip install -r requirements.txt` |
| `.\venv\Scripts\Activate.ps1 cannot be loaded` | PowerShell execution policy | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, retry |
| `Cannot reach relay at 127.0.0.1:9999` | relay not running | start tab 1 (`python server\relay.py`) first |
| Garbled UI / broken borders | running in legacy `cmd.exe` | switch to Windows Terminal |
| `FileNotFoundError: keys\...` or `data\...` | launched from wrong folder | `cd` to repo root (`call-of-ssh\`), run `python client\main.py alice` from there |
| `python` opens Microsoft Store | Store stub on PATH, real Python missing/misconfigured | install from python.org with "Add to PATH" ticked |
| Firewall pop-up on relay start | normal first-run behavior | click Allow (or Keep blocking for same-PC-only demo) |

---

## Quick reference: full setup in one block

For a fresh machine (PowerShell, run line by line the first time):

```powershell
# 0. install python.org Python 3.11+ (PATH ticked), Windows Terminal, git, OpenSSH Client

git clone https://github.com/Swanand-Vidyasagar73/call-of-ssh.git
cd call-of-ssh
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

mkdir keys, data
ssh-keygen -t ed25519 -f keys\alice_id_ed25519 -C "alice" -N '""'
ssh-keygen -t ed25519 -f keys\bob_id_ed25519 -C "bob" -N '""'
Get-Content keys\alice_id_ed25519.pub | Add-Content keys\authorized_keys
Get-Content keys\bob_id_ed25519.pub | Add-Content keys\authorized_keys
python client\identity.py

# then in 3 tabs:
python server\relay.py
python client\main.py alice
python client\main.py bob
```

---

## Linux ↔ Windows differences (summary)

| Area | Linux (Arch guide) | Windows (this guide) |
|---|---|---|
| Deps | `paramiko`, `cryptography` | same + auto `windows-curses` |
| venv activate | `source venv/bin/activate` | `.\venv\Scripts\Activate.ps1` |
| Keygen | `ssh-keygen ... -N ""` | `ssh-keygen ... -N '""'` |
| Append pubkeys | `cat ... >> authorized_keys` | `Get-Content ... \| Add-Content ...` |
| Plaintext check | `strings data/*.dat \| grep` | `Select-String -Path data\*.dat` |
| Netem testing | `tc qdisc ... netem` | Clumsy, or `flaky_send()` |
| Terminal | any real terminal | Windows Terminal / PowerShell (not `cmd.exe`) |
| Python code | — | **zero changes needed** |
