import logging
import json
import requests
import socket
import selectors
import types
import argparse

API_URL = 'https://opentdb.com/api.php?amount=1&type=boolean'
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = set()
        self.question = self.fetch_question()
        
    def fetch_question(self):
        response = requests.get(API_URL)
        question = response.json().get('results', [])
        logging.info(f'Fetched {len(question)} trivia questions.')
        return question
    
    def creat_server_socket(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        logging.info(f'Starting server...\nListening on {self.host}:{self.port}')
        server_socket.setblocking(False)
        self.sel.register(server_socket, selectors.EVENT_READ, self.accept_connections)
        return server_socket

    def accept_connections(self, sock):
        conn, addr = sock.accept()
        logging.info(f'Accepting connection from {addr}')
        self.clients.add(conn)
        conn.setblocking(False)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, self.handle_client)
        
    
def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Server', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, help='The IP address to bind the server')
    parser.add_argument('p', '--port', type=int, required=True, help='The port to bind the server')
    parser.add_argument('h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()