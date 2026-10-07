# Call of SSH — What To Do Next (step-by-step)

Current state: UI ✓, storage ✓, relay ✓, but **relay sees plaintext** and **anyone can spoof any username**. Steps below are in priority order. Do 0→2 minimum; 3 strongly recommended; rest as time allows.

---

## Step 0 — Sanity-run what exists (10 min)
**Why:** confirm the demo works before changing anything.

```bash
cd /home/user/call-of-ssh
# terminal 1
python3 server/relay.py
# terminal 2
python3 client/main.py alice   # target: bob / any passphrase
# terminal 3
python3 client/main.py bob     # target: alice / its own passphrase
```
- [ ] Alice→Bob and Bob→Alice messages appear in both TUIs
- [ ] `ls -l data/` shows `alice_chat.dat`, `bob_chat.dat`; restart a client with same passphrase → history replays
- [ ] Kill relay (`Ctrl+C`), restart it → server has zero history (proves statelessness), clients still have theirs

---

## Step 1 — Small fixes & hygiene (30 min)
**Why:** close silly gaps and fix two real framing bugs before building on top.

1. **Register Bob.** `keys/user_registry.json` has only Alice. Either run:
   ```bash
   python3 -c "from client.identity import register_user; print(register_user('bob','keys/bob_id_ed25519.pub'))"
   ```
   (run from repo root) or edit `client/identity.py` `__main__` to register both users in a loop.
2. **Fix relay framing bug** (`server/relay.py`): it does `data.partition(b"|")` on each raw `recv()` chunk, so two messages arriving together corrupt each other. Fix: per-client byte buffer, handshake line `username\n`, then route line-by-line:
   ```python
   buf = b""; username = None
   while True:
       chunk = conn.recv(4096)
       if not chunk: break
       buf += chunk
       if username is None:
           if b"\n" not in buf: continue
           line, buf = buf.split(b"\n", 1)
           username = line.decode().strip()  # register peer
           continue
       while b"\n" in buf:
           line, buf = buf.split(b"\n", 1)
           target, _, payload = line.partition(b"|")
           # sendall(payload + b"\n") to target if online
   ```
3. **Match it in `client/main.py`:** send handshake as `(USERNAME + "\n").encode()`. `on_send` already ends with `\n` (from `make_message`), so each send is one line — good.
4. **Graceful errors:** wrap `sock.connect` in try/except ("relay not running? start `server/relay.py` first"), catch `BrokenPipeError` on send, `KeyboardInterrupt` → close socket cleanly.
5. **Pin deps:** `pip freeze | grep -iE "paramiko|cryptography"` → write exact versions into `requirements.txt`.
- [ ] Verify: send 20 rapid messages Alice→Bob; all arrive complete and in order (framing fix works)

---

## Step 2 — E2E content encryption (1–2 hrs) ⭐ MOST IMPORTANT
**Why:** today the relay sees plaintext JSON — this kills your core thesis ("server can't read messages"). Fix it.

1. In `client/message.py`, add encrypt/decrypt of just the `content` field using a **shared chat passphrase** (exchanged out-of-band, e.g. in person):
   ```python
   import os, base64
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   from storage import derive_key  # reuse PBKDF2
   CHAT_SALT = b"call-of-ssh-chat-v1"  # constant salt so both peers derive same key (demo-grade)

   def seal(content, chat_key):
       nonce = os.urandom(12)
       ct = AESGCM(chat_key).encrypt(nonce, content.encode(), None)
       return base64.b64encode(nonce + ct).decode()

   def open_box(sealed, chat_key):
       raw = base64.b64decode(sealed)
       return AESGCM(chat_key).decrypt(raw[:12], raw[12:], None).decode()
   ```
2. In `client/main.py`: `chat_pass = getpass("Chat passphrase (shared with peer): ")`, `chat_key = derive_key(chat_pass, CHAT_SALT)`; `seal()` before `make_message`, `open_box()` after `parse_message` (wrap in try/except → show `[undecryptable]`).
3. **Keep storage passphrase separate** from chat passphrase (two prompts — correct design).
- [ ] Verify: add temp `print(data)` in relay or sniff with `tcpdump -A -i lo port 9999` → relay sees only base64 blobs, never plaintext. Clients still chat normally.
- Limitation to note in writeup: shared passphrase, no forward secrecy — fine for demo, ECDH per-user keys are future work.

---

## Step 3 — Relay authentication (1–2 hrs)
**Why:** today anyone can connect claiming `alice` and hijack her messages. Prove identity with the SSH keys you already have.

1. Challenge-response in `server/relay.py` + `client/main.py` using existing ed25519 keys:
   - Relay → client: random 32-byte nonce (hex).
   - Client: signs nonce with its private key (`keys/<user>_id_ed25519`) via `cryptography.hazmat.primitives.asymmetric.ed25519` (`load_ssh_private_key`), sends signature.
   - Relay: loads `keys/authorized_keys`, finds the line whose comment matches claimed username, verifies with `load_ssh_public_key`; reject + close on failure.
2. Also reject duplicate logins (if `alice` already connected, refuse second `alice`).
- [ ] Verify: legit Alice connects; edited/spoofed client claiming `alice` without her private key gets rejected.

---

## Step 4 — Decide offline behavior (30–60 min)
**Why:** currently offline-target messages vanish silently — worst of both worlds.

- **Cheap (recommended for demo):** relay replies `ERROR|user-offline\n` to sender when target missing; client shows `[bob is offline — not delivered]`. Stays stateless, honest UX.
- **Full:** in-memory per-user pending queue, delivered on reconnect, capped (e.g. 50 msgs) + TTL. Only do this if time permits.
- [ ] Verify: send to offline Bob → Alice sees the notice; no silent loss.

---

## Step 5 — Client UX polish (1 hr)
**Why:** demo quality; hardcoded `alice|bob` + fixed target looks unfinished.

1. Accept any username: `USERNAME = sys.argv[1]`, check `keys/<user>_id_ed25519` exists, else exit with hint to `ssh-keygen`.
2. Commands in input box: `/switch <user>` (change target), `/who` (ask relay for online list — add `LIST|` protocol), `/clear`, `/quit` (close socket, restore terminal).
3. Show timestamps (`[14:02] alice: hi`) and `[you]` vs peer styling.
- [ ] Verify: third user `carol` can keygen + chat without code changes.

---

## Step 6 — Testing with evidence (1–2 hrs)
**Why:** claims need proof for the writeup/demo.

| # | Test | Command / action | Must see |
|---|------|------------------|----------|
| 1 | Storage locked | open `.dat` with wrong passphrase | `InvalidTag` exception, no garbage |
| 2 | No plaintext at rest | `strings data/alice_chat.dat \| grep -i "hello"` | empty output |
| 3 | Relay blind (after Step 2) | relay `print(data)` / tcpdump | only base64 blobs |
| 4 | Framing | 20 rapid sends | all arrive, in order, none garbled |
| 5 | Loss/latency | `sudo tc qdisc add dev lo root netem delay 200ms loss 5%` → chat → `sudo tc qdisc del dev lo root netem` | messages still reassemble (buffer logic) |
| 6 | Stateless relay | kill relay mid-chat, restart | server empty, client history intact |
| 7 | Spoof rejected (after Step 3) | fake-username client | connection refused |

Save outputs/screenshots into `TESTING.md`.

---

## Step 7 — Docs & threat-model writeup (1–2 hrs)
**Why:** this is what gets graded/demoed.

1. `README.md`: what it is, 5-min setup (link Arch guide), how to run 3 terminals, features + honest limits.
2. Threat-model table, each row = mechanism + evidence:
   - **Transport:** (after Step 2) E2E AES-GCM content; relay routes blind blobs — evidence: Test 3.
   - **Storage:** AES-GCM + PBKDF2 200k — evidence: Tests 1–2.
   - **Identity:** ed25519 challenge-response (after Step 3), no passwords/SIM — evidence: Test 7.
   - **Server trust:** in-memory only, kill = wipe — evidence: Test 6.
   - **Auditability:** ~400 lines of readable Python vs closed-source apps.
   - **Honest limits:** no forward secrecy, shared chat passphrase, offline drops (or capped queue), no group chat — all listed as future work.

---

## Step 8 — Cleanup & release (20 min)
**Why:** don't ship junk; prove fresh-machine setup works.

1. `git status` must show only code/docs — never `keys/`, `data/`, `venv/` (already gitignored; don't force-add).
2. Delete the 38 MB `venv/` from any zip you share; receiver rebuilds via `pip install -r requirements.txt`.
3. Fresh-test: new folder → `git clone` → follow Arch guide top-to-bottom → 3-terminal chat works.
4. `git tag v0.2-relay-e2e` (or similar) after Steps 2–3 land.

---

## Explicitly OUT of scope (don't start these yet)
Group chat, file transfer, voice, GUI/mobile client, per-message ECDH + forward secrecy, persistent offline spool on disk — all legitimate future work, all will dilute the demo if started now.

**Suggested order if short on time:** Step 0 → Step 1 → Step 2 → Step 6 (tests 1–4) → Step 7. That alone is a complete, defensible demo.
