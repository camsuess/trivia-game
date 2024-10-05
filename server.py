import logging
import json
import requests
import socket
import selectors
import types
import argparse

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = set()
        

def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Server', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, help='The IP address to bind the server')
    parser.add_argument('p', '--port', type=int, required=True, help='The port to bind the server')
    parser.add_argument('h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()