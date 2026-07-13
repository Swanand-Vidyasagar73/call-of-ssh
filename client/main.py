import time
import json

def make_message(sender, content):
    return json.dumps({
        "sender": sender,
        "timestamp": time.time(),
        "content": content
    }) + "\n"

def parse_message(line):
    data = json.loads(line)
    return data["sender"], data["timestamp"], data["content"]