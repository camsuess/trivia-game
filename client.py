import socket
import selectors
import argparse
import logging
import json

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port


def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Client', add_help=False)
    
    parser.add_argument('i', '--ip', type=str, help='Server IP')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server Port')
    parser.add_argument('h', '--help', action=help, help='Show help message and exit')
    
    return parser.parse_args()