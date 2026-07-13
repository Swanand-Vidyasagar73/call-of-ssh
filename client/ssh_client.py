import paramiko
def connect(host, port, username, key_path):
    key = paramiko.Ed25519Key.from_private_key_file(key_path)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname = host, port = port, username = username, pkey = key)
    return client

def open_shell_channel(client):
    channel = client.invoke_shell()
    return channel

if __name__ == "__main__":
    client = connect("127.0.0.1", 2222, "swanand", "keys/alice_id_ed25519")
    chan = open_shell_channel(client)

    chan.send("echo hello-over-ssh\n")
    import time
    time.sleep(1)
    print(chan.recv(4096).decode())

    client.close()

