import socket
import selectors
import argparse
import logging
from message import Message

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.client_socket = self.create_client_socket()
    
    def create_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        return client_socket

def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Client', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, default='127.0.0.1', help='Server IP')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server Port')
    parser.add_argument('-h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    client = GameClient(host=args.ip, port=args.port)
    
    try:
        client.start()
    finally:
        client.close()
