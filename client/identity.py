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
        json.dump(registry, f, indent = 2)

    return fp


def lookup_username(fingerprint):
    with open(USER_REGISTRY_PATH) as f:
        registry = json.load(f)
    return registry.get(fingerprint, "unknown")


if __name__ == "__main__":
    fp = register_user("alice", "keys/alice_id_ed25519.pub")
    print(f"Registered Alice as {fp}")
    print(lookup_username(fp))