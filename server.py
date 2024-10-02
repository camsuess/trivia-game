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






















# import socket
# import selectors
# import types
# import argparse
# import sys

# class EchoServer:
#     def __init__(self, host, port):
#         self.selector = selectors.DefaultSelector()
#         self.host = host
#         self.port = port

#     def start(self):
#         # Create a TCP/IP socket
#         server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         server_sock.bind((self.host, self.port))
#         server_sock.listen()
#         print(f"Server started, listening on {self.host}:{self.port}")
#         server_sock.setblocking(False)
        
#         # Register the socket to be monitored for incoming connections
#         self.selector.register(server_sock, selectors.EVENT_READ, data=None)

#         try:
#             while True:
#                 events = self.selector.select(timeout=None)  # Blocking call, waits for events
#                 for key, mask in events:
#                     if key.data is None:
#                         # New connection, accept it
#                         self.accept_connection(key.fileobj)
#                     else:
#                         # Existing connection, handle it
#                         self.handle_client(key, mask)
#         except KeyboardInterrupt:
#             print("Server stopped")
#         finally:
#             self.selector.close()

#     def accept_connection(self, sock):
#         client_sock, addr = sock.accept()  # Accept new connection
#         print(f"Accepted connection from {addr}")
#         client_sock.setblocking(False)
        
#         # Create a SimpleNamespace object to store client info
#         data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
        
#         # Register the client socket for READ events
#         self.selector.register(client_sock, selectors.EVENT_READ, data=data)

#     def handle_client(self, key, mask):
#         sock = key.fileobj
#         data = key.data

#         if mask & selectors.EVENT_READ:
#             recv_data = sock.recv(1024)  # Read up to 1024 bytes
#             if recv_data:
#                 data.outb += recv_data
#                 print(f"Received data from {data.addr}: {recv_data.decode()}")
                
#                 # Modify the registration to handle write events
#                 self.selector.modify(sock, selectors.EVENT_WRITE, data=data)
#             else:
#                 print(f"Closing connection to {data.addr}")
#                 self.selector.unregister(sock)
#                 sock.close()

#         if mask & selectors.EVENT_WRITE:
#             if data.outb:
#                 sent = sock.send(data.outb)  # Echo back the data
#                 print(f"Sent {sent} bytes back to {data.addr}")
#                 data.outb = data.outb[sent:]  # Remove the sent data
                
#                 # If there's nothing left to send, modify to listen for read events again
#                 if not data.outb:
#                     self.selector.modify(sock, selectors.EVENT_READ, data=data)


# def parse_args():
#     parser = argparse.ArgumentParser(description="Run a simple echo server.")
    
#     parser.add_argument(
#         '-i', '--ip', type=str, default='127.0.0.1',
#         help="The IP address to bind the server (default: 127.0.0.1)"
#     )
#     parser.add_argument(
#         '-p', '--port', type=int, required=True,
#         help="The port to bind the server"
#     )
#     parser.add_argument(
#         '-h', '--help', action='help', default=argparse.SUPPRESS,
#         help="Show this help message and exit"
#     )

#     return parser.parse_args()


# # Example of starting the server with command-line arguments
# if __name__ == "__main__":
#     args = parse_args()

#     # Start the server with the provided IP and port
#     server = EchoServer(host=args.ip, port=args.port)
#     server.start()




# parse_args() function:

# This function uses the argparse module to parse command-line arguments for the server.
# -i / --ip: Specifies the host IP address. It defaults to 127.0.0.1 (localhost) if not provided.
# -p / --port: Specifies the port the server will bind to. This is a required argument.
# -h / --help: Automatically provided by argparse, displays help information and usage.



# start server commands
# python server.py -i 192.168.1.10 -p 65432
# python server.py -p 65432 (localhost)
# python server.py -h (for server info before starting the server)