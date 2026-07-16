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
            f.write(self.salt + nonce +ciphertext)

    def append(self, sender, timestamp, content):
        self.messages.append({"sender": sender, "timestamp": timestamp, "content": content})
        self.save_all()

if __name__ == "__main__":
    import getpass
    passphrase = getpass.getpass("Enter storage passphrase: ")
    store = EncryptedFlatStore("data/alic_chat.dat", passphrase)
    store.append("alice", 1234567890.0, "hello")
    print("Saved. Stored messages stored so far: ")
    for m in store.messages:
        print(m)
