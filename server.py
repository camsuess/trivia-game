import logging
import json
import requests
import socket
import selectors
import argparse
import message

API_URL = 'https://opentdb.com/api.php?amount=1&type=boolean'
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = {}
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
        conn.setblocking(False)
        self.clients[conn] = {'address': addr, 'name': None, 'score': 0}
        self.send_name_prompt(conn)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, self.handle_client)
        
    def send_question(self, conn=None):
        if self.question:
            data = {
            'question': self.question['question'],
            'choices': self.question['incorrect_answers'] + [self.question['correct_answer']],
            }
            for client_conn in self.clients:
                message.send(client_conn, data)
    
    def process_answer(self, conn, data):
        if data['answer'] == self.question['correct_answer']:
            response = "Correct!"
            self.clients[conn]['score'] += 1
        else:
            response = f"Wrong! The correct answer was {self.question['correct_answer']}."
        
        self.notify_all(f"{self.clients[conn]['name']} answered: {response}")
        message.send(conn, {"message": f"Your current score: {self.clients[conn]['score']}"})
        for client_conn in self.clients:
            message.send(client_conn, {"message": f"{self.clients[client_conn]['name']}'s current score: {self.clients[client_conn]['score']}"})
            
    def send_name_prompt(self, conn):
        message.send(conn, {"message": "Please enter your name:"})
        
    def notify_all(self, message, exclude_conn=None):
        for conn in self.clients:
            if conn != exclude_conn: # exclude the player that triggered the message
                conn.send(json.dumps({"message": message}).encode('utf-8'))
                
    def disconnect_client(self, conn):
        player_name = self.clients[conn]['name']
        self.sel.unregister(conn)
        self.clients.pop(conn, None)
        conn.close()
        if player_name:
            self.notify_all(f"Player {player_name} has left the game.")
    
    def handle_client(self, conn):
        try:
            message = conn.recv(1024).decode('utf-8')
            if message:
                logging.info(f'Received message: {message}')
                data = json.loads(message)
                if self.clients[conn]['name'] is None:
                    self.clients['name'] = data['name']
                    logging.info(f"Player {data['name']} joined from {self.clients[conn]['address']}")
                    self.send_question(conn)
                    self.notify_all(f"{data['name']} just joined the game!")
            else:
                self.disconnect_client(conn)
        except BlockingIOError:
            pass
        except ConnectionResetError:
            self.disconnect_client(conn)
    
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
