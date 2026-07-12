# Call of SSH — Arch Linux Setup & Implementation Guide

Complete guide for setting up and running Call of SSH on a fresh Arch Linux install, using your actual repo: `https://github.com/Swanand-Vidyasagar73/call-of-ssh`

---

## Part 1: System setup (fresh Arch)

### Step 1.1 — Update the system

Always do this first on a fresh Arch install:

```bash
sudo pacman -Syu
```

### Step 1.2 — Install required packages

```bash
sudo pacman -S git python python-pip openssh base-devel github-cli
```

What each one does:

| Package | Purpose |
|---|---|
| `git` | clone and manage your repo |
| `python` | Arch ships a current Python 3 |
| `python-pip` | install paramiko/cryptography inside a venv |
| `openssh` | gives you `sshd` (server) plus `ssh`/`ssh-keygen` (client) |
| `base-devel` | compiler toolchain — `cryptography` sometimes needs to build native components |
| `github-cli` | (`gh`) simplest way to authenticate with GitHub |

Note: `curses` needs nothing extra — it's part of Python's standard library on Linux.

---

## Part 2: GitHub authentication

You need this before you can push any changes back to your repo.

```bash
gh auth login
```

Answer the prompts like this:
- **Account** → GitHub.com
- **Protocol** → HTTPS (simplest) or SSH (optional, matches the project's key-based theme)
- **Authenticate Git with your GitHub credentials?** → Yes
- **How would you like to authenticate?** → "Login with a web browser" — it gives you a one-time code and a URL; open it, paste the code, approve.

Then set your commit identity (use the email tied to your GitHub account):

```bash
git config --global user.name "Swanand Vidyasagar"
git config --global user.email "your_email@example.com"
```

Verify it worked:

```bash
gh auth status
```

---

## Part 3: Clone the repo and set up the environment

### Step 3.1 — Clone

```bash
git clone https://github.com/Swanand-Vidyasagar73/call-of-ssh.git
cd call-of-ssh
```

### Step 3.2 — Create a virtual environment

Arch's system `pip` is externally-managed and will refuse a bare `pip install` — a venv is required, not just recommended:

```bash
python -m venv venv
source venv/bin/activate
```

You'll know it's active when your prompt shows `(venv)` at the start.

### Step 3.3 — Fix `requirements.txt` for Linux

Your `requirements.txt` has `windows-curses` in it, which only exists for Windows and has no Linux build — installing it as-is will fail. Remove that line:

```bash
sed -i '/windows-curses/d' requirements.txt
```

If you want to preserve cross-platform use of the repo (e.g. you still use the Windows track sometimes), do it as an install-time filter instead of editing the tracked file:

```bash
grep -v windows-curses requirements.txt | pip install -r /dev/stdin
```

Otherwise, just install normally after the edit:

```bash
pip install -r requirements.txt
```

### Step 3.4 — Commit the fix (optional but recommended)

If you edited `requirements.txt` directly:

```bash
git add requirements.txt
git commit -m "Remove windows-curses for Linux compatibility"
git push
```

---

## Part 4: Generate keys and set up a local SSH test server

Your `.gitignore` excludes `keys/` and `data/` — private keys and encrypted chat data shouldn't live in git — so you regenerate these fresh on every machine.

### Step 4.1 — Generate ed25519 keypairs

```bash
mkdir -p keys data
ssh-keygen -t ed25519 -f keys/alice_id_ed25519 -C "alice" -N ""
ssh-keygen -t ed25519 -f keys/bob_id_ed25519 -C "bob" -N ""
```

### Step 4.2 — Register public keys

```bash
cat keys/alice_id_ed25519.pub >> keys/authorized_keys
cat keys/bob_id_ed25519.pub >> keys/authorized_keys
chmod 600 keys/authorized_keys
```

### Step 4.3 — Set up a dedicated test SSH instance (port 2222)

Keeping this separate from your normal login SSH avoids touching real system config.

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
sudo /usr/bin/sshd -f ~/call-of-ssh-test/etc/sshd_config -D
```

Replace `YOUR_USER` with your actual username in both `HostKey` and `AuthorizedKeysFile` lines. `-D` runs it in the foreground so you can watch logs and Ctrl+C when done. Note the binary path is `/usr/bin/sshd` on Arch (not `/usr/sbin/sshd` like Debian/Ubuntu).

If you'd rather run your system's main `sshd` permanently instead of a foreground test instance:

```bash
sudo systemctl enable sshd
sudo systemctl start sshd
sudo systemctl status sshd
```

...then point `AuthorizedKeysFile` in `/etc/ssh/sshd_config` at your project's `keys/authorized_keys`, and restart with `sudo systemctl restart sshd`.

### Checkpoint

```bash
ssh -i keys/alice_id_ed25519 -p 2222 YOUR_USER@127.0.0.1
```

You should get a shell prompt with no password asked. `Ctrl+D` to exit. If this works, your key-based auth is wired correctly and the client code will connect the same way.

---

## Part 5: Run the app

```bash
source venv/bin/activate   # if not already active
python client/main.py      # adjust if your repo's entry point differs
```

Open a second terminal, activate the venv again, and run the second user's client to chat between them.

---

## Part 6: Testing (Arch-specific notes)

Since you're on real Linux (not WSL), everything works with zero substitutions:

- **`tc netem`** for latency/packet-loss simulation works natively here (it didn't reliably apply under WSL's virtualized networking):
  ```bash
  sudo tc qdisc add dev lo root netem delay 200ms loss 5%
  # run your test
  sudo tc qdisc del dev lo root netem   # remove when done
  ```
- **Storage unreadability check**:
  ```bash
  strings data/alice_chat.dat | grep -i "hello"
  ```
  This should return nothing if your AES-GCM encryption is working — if your test message text shows up, something's wrong.
- **`curses`** needs no extra package on Arch, and any real terminal (not a minimal serial console) will render it fine.

---

## Quick reference: full setup in one block

For when you're doing this again on a new machine/VM:

```bash
sudo pacman -Syu
sudo pacman -S git python python-pip openssh base-devel github-cli
gh auth login
git config --global user.name "Swanand Vidyasagar"
git config --global user.email "your_email@example.com"

git clone https://github.com/Swanand-Vidyasagar73/call-of-ssh.git
cd call-of-ssh
python -m venv venv
source venv/bin/activate
sed -i '/windows-curses/d' requirements.txt
pip install -r requirements.txt

mkdir -p keys data
ssh-keygen -t ed25519 -f keys/alice_id_ed25519 -C "alice" -N ""
ssh-keygen -t ed25519 -f keys/bob_id_ed25519 -C "bob" -N ""
cat keys/alice_id_ed25519.pub >> keys/authorized_keys
cat keys/bob_id_ed25519.pub >> keys/authorized_keys
chmod 600 keys/authorized_keys
```

Then set up the test `sshd` instance from Part 4, Step 4.3, and run the app.
