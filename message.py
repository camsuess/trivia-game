import json

class Message:
    
    @staticmethod
    def encode(data):
        return json.dumps(data).encode('utf-8')
    
    @staticmethod
    def decode(data):
        return json.loads(data.decode('utf-8'))
    
    @staticmethod
    def send(conn, data):
        conn.send(Message.encode(data))
        
    @staticmethod
    def receive(conn):
        try:
            data = conn.recv(1024)
            if not data:
                return None
            return Message.decode(data)
        except (json.JSONDecodeError, ConnectionResetError):
            return None
