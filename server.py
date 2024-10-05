import logging
import json
import requests
import socket
import selectors
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
        self.server_socket = self.create_server_socket()
        
    def fetch_question(self):
        response = requests.get(API_URL)
        question = response.json().get('results', [])
        logging.info(f'Fetched {len(question)} trivia questions.')
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

    def accept_connections(self, sock):
        conn, addr = sock.accept()
        logging.info(f'Accepting connection from {addr}')
        self.clients.add(conn)
        conn.setblocking(False)
        self.send_question(conn)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, self.handle_client)
        
    def send_question(self, conn):
        if self.question:
            data = {
            'question': self.question['question'],
            'choices': self.question['incorrect_answers'] + [self.question['correct_answer']],
            'correct_answer': self.question['correct_answer']
            }
            conn.send(json.dumps(data).encode('utf-8'))
    
    def handle_client(self, conn):
        try:
            message = conn.recv(1024).decode('utf-8')
            if message:
                logging.info(f'Received message: {message}')
                data = json.loads(message)
                if data['answer'] == data['correct_answer']:
                    response = "Correct!"
                else:
                    response = f"Wrong! The correct answer was {data['correct_answer']}."
                
                conn.send(response.encode('utf-8'))
            else:
                self.sel.unregister(conn)
                self.clients.remove(conn)
                conn.close()
        except BlockingIOError:
            pass
        except ConnectionResetError:
            self.sel.unregister(conn)
            self.clients.remove(conn)
            conn.close()
    
    def start(self):
        while True:
            events = self.sel.select(timeout=True)
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)
    
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
