import sys
import requests
import json
import socket
import selectors
import types

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
    
    def start(self):
        # creat a TCP socket
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # should prevent address already in use error
        server_sock.bind((self.host, self.port))
        server_sock.listen()
        server_sock.setblocking(False)
        self.sel.register(server_sock, self.sef.EVENT_READ, data=None) #register the socket to be monitored for incoming connections
        print(f"Server starting...\n Listening on {self.host}:{self.port}")
        
        # main event loop
        try:
            while True:
                events = self.sel.select(timeout=True) # blocking call, waits for events
                for key, mask in events:
                    if key.data is None:
                        self.accept_connection(key.fileobj)
                    else:
                        self.handle_client(key, mask)
        except KeyboardInterrupt:
            print("Interrupted rudly by the keyboard, exiting...")
        finally:
            self.sel.close()
    
    # accept_connections method
    def accept_connections(self, sock):
        client_sock, addr = sock.accept
        print(f"Accepted connection from {addr}")
        client_sock.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
        events = self.sel.EVENT_READ | self.self.EVENT_WRITE
        self.sel.register(client_sock, events, data=data)
    # handle_clients method

# parse_args method
            
# main
