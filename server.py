import logging
import json
import requests
import socket
import selectors
import argparse
from message import Message

API_URL = 'https://opentdb.com/api.php?amount=1&type=boolean'
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameState:
    WAITING = "waiting"
    ASKING_QUESTION = "asking"
    FINISHED = "finished"

class Player:
    def __init__(self, conn, addr):
        self.conn = conn
        self.address = addr
        self.name = None
        self.score = 0

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = {}
        self.question = None
        self.game_state = GameState.WAITING
        self.server_socket = self.create_server_socket()
        
    def fetch_question(self):
        response = requests.get(API_URL)
        question = response.json().get('results', [])
        logging.info(f'Fetched {len(question)} trivia questions.')
        logging.info(f'Fetched question data: {question}')
        return question[0] if question else None  # return the first question or None
    
    def create_server_socket(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        logging.info(f'Starting server...\nListening on {self.host}:{self.port}')
        server_socket.setblocking(False)
        self.sel.register(server_socket, selectors.EVENT_READ, self.accept_connections)
        return server_socket

    def accept_connections(self, sock, mask):
        conn, addr = sock.accept()
        logging.info(f'Accepting connection from {addr}')
        conn.setblocking(False)
        self.clients[conn] = Player(conn, addr)
        self.send_name_prompt(conn)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, self.handle_client)
    
    def send_name_prompt(self, conn):
        prompt = {
            "action": "set_name",
            "message": "Please enter your username: "
        }
        Message.send(conn, prompt)
    
    def handle_client(self, conn, mask):
        if mask & selectors.EVENT_READ:
            message = Message()
            message.read(conn)
            if message.request:
                self.process_request(conn, message.request)
        if mask & selectors.EVENT_WRITE:
            message = Message()
            message.write(conn)
    
    def process_request(self, conn, request):
        if request['action'] == "set_name":
            player = self.clients[conn]
            player.name = request.get('name')
            logging.info(f"Player {player.name} connected from {player.address}.")
            self.send_question(conn)
            
    def send_question(self, conn):
        question = self.fetch_question()
        question_message = {
            "action": "question",
            "question": question['question'],
            "correct_answer": question['correct_answer']  # Include correct answer for validation
        }
        Message.send(conn, question_message)
        
    def start(self):
        try:
            while True:
                events = server.sel.select()
                for key, _ in events:
                    callback = key.data
                    callback(key.fileobj, key.events)
        except KeyboardInterrupt:
            logging.info("Server shutting down.")
        finally:
            server.sel.close()
    
def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Server', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, default='127.0.0.1', help='The IP address to bind the server')
    parser.add_argument('-p', '--port', type=int, required=True, help='The port to bind the server')
    parser.add_argument('-h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    server = GameServer(host=args.ip, port=args.port)
    server.start()
