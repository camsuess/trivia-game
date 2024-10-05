import socket
import selectors
import argparse
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
    
    def creat_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        return client_socket
    
    


def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Client', add_help=False)
    
    parser.add_argument('i', '--ip', type=str, help='Server IP')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server Port')
    parser.add_argument('h', '--help', action=help, help='Show help message and exit')
    
    return parser.parse_args()