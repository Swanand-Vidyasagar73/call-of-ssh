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

