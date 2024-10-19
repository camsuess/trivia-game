import json

class Message:
    
    def encode(data):
        return json.dumps(data).encode('utf-8')
    
    def decode(data):
        return json.loads(data).decode('utf-8')
    
    def send(conn, data):
        conn.send(Message.encode(data))
        
    def receive(conn):
        return Message.decode(conn.recv(1024))