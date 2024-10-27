import json
import struct
import io

class Message:
    def __init__(self):
        self._recv_buffer = b""            # Buffer for incoming data
        self._send_buffer = b""            # Buffer for outgoing data
        self._jsonheader_len = None        # Length of the JSON header
        self.jsonheader = None              # Parsed JSON header
        self.request = None                 # The actual request data
        self.response_created = False        # Flag for response creation
        
    def _json_encode(self, obj, encoding): # Encode the object as a JSON byte string
        return json.dumps(obj, ensure_ascii=False).encode(encoding)
    
    def _json_decode(self, json_bytes, encoding): # Decode the JSON byte string back into a Python object
        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
        obj = json.loads(tiow.read())
        tiow.close()
        return obj
    
    def create_message(self, content): # Create a message with a json header
        content_bytes = self._json_encode(content, "utf-8")
        jsonheader = {
            "content-length": len(content_bytes),
            "content-type": "text/json",
            "content-encoding": "utf-8",
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        return message_hdr + jsonheader_bytes + content_bytes
    
    def read(self, sock): # Read data from the socket
        try:
            data = sock.recv(4096)
            if data:
                self._recv_buffer += data
                self.process_buffer()
            else:
                self.close(sock)  # Handle disconnection
        except BlockingIOError:
            pass  # Resource temporarily unavailable

    def write(self, sock): # Write data to the socket
        if self._send_buffer:
            sent = sock.send(self._send_buffer)
            self._send_buffer = self._send_buffer[sent:]

    def process_buffer(self): # Process the incoming data in the buffer
        if self._jsonheader_len is None and len(self._recv_buffer) >= 2:
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:2])[0]
            self._recv_buffer = self._recv_buffer[2:]

        if self._jsonheader_len is not None and self.jsonheader is None:
            if len(self._recv_buffer) >= self._jsonheader_len:
                self.jsonheader = self._json_decode(self._recv_buffer[:self._jsonheader_len], "utf-8")
                self._recv_buffer = self._recv_buffer[self._jsonheader_len:]

        if self.jsonheader and self.request is None:
            content_length = self.jsonheader["content-length"]
            if len(self._recv_buffer) >= content_length:
                self.request = self._json_decode(self._recv_buffer[:content_length], "utf-8")
                self._recv_buffer = self._recv_buffer[content_length:]
                self._set_send_buffer()

    def _set_send_buffer(self): # Prepare a response based on the request
        if self.request:
            response_content = {"result": "This is a response to your request."}  # Example response
            self._send_buffer = self.create_message(response_content)
            self.response_created = True
            
    @staticmethod
    def send(sock, message_content):
        message = Message()
        message._send_buffer = message.create_message(message_content)
        message.write(sock)

    def close(self, sock): # Close the socket connection
        sock.close()
        self._recv_buffer = b""  # Clear buffers
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
    
    
    
