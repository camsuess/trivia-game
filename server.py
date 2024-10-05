import logging
import json
import requests
import socket
import selectors
import types
import argparse

API_URL = 'https://opentdb.com/api.php?amount=1&type=boolean'

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
        

def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Server', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, help='The IP address to bind the server')
    parser.add_argument('p', '--port', type=int, required=True, help='The port to bind the server')
    parser.add_argument('h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()