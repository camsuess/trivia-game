import logging
import json
import requests
import socket
import selectors
import argparse
from message import Message
import time

API_URL = 'https://opentdb.com/api.php?amount=50&type=boolean'

logging.basicConfig(level=logging.DEBUG, 
                    format='%(levelname)s - %(message)s',
                    filename='server.log'
                    )

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
        self.answered = False

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = {}
        self.question_queue = []
        self.question = None
        self.game_state = GameState.WAITING
        self.server_socket = self.create_server_socket()
    
    def create_server_socket(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        logging.info(f'Starting server...\nListening on {self.host}:{self.port}\n')
        server_socket.setblocking(False)
        self.sel.register(server_socket, selectors.EVENT_READ, self.accept_connections)
        self.question = self.fetch_question()
        return server_socket

    def accept_connections(self, sock, mask):
        conn, addr = sock.accept()
        logging.info(f'Accepting connection from {addr}')
        conn.setblocking(False)
        
        if conn in self.clients:
            self.sel.unregister(conn)
            self.clients[conn].conn.close()
            self.clients.pop(conn, None)
        
        self.clients[conn] = Player(conn, addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, self.handle_client)
        self.send_name_prompt(conn)
    
    def send_name_prompt(self, conn):
        prompt = {
            "action": "set_name",
            "message": "Please enter your username: "
        }
        Message.send(conn, prompt)
    
    def handle_client(self, conn, mask):
        try:
            if mask & selectors.EVENT_READ:
                message = Message()
                message.read(conn)
                if message.request:
                    self.process_request(conn, message.request)
            if mask & selectors.EVENT_WRITE:
                message = Message()
                message.write(conn)
        except (ConnectionResetError, BrokenPipeError):
            logging.info(f"Connection lost with {self.clients[conn].name}")
            self.sel.unregister(conn)
            conn.close()
            self.clients.pop(conn, None)
    
    def process_request(self, conn, request):
        player = self.clients[conn]
        
        if request['action'] == "disconnect":
            logging.info(f'\nPlayer {player.name} disconnected from the server.\n')
            self.sel.unregister(conn)
            conn.close()
            self.clients.pop(conn, None)
            
            if all(player.answered for player in self.clients.values()):
                logging.info(f'All players have answered')
                self.notify_scores() 
                self.reset_for_next_question()
                self.send_question()
        
        if request['action'] == "set_name":
            player.name = request.get('name')
            logging.info(f"Player {player.name} connected from {player.address}.")
            self.game_state = GameState.ASKING_QUESTION
            
            if self.game_state == GameState.ASKING_QUESTION and self.question:
                self.send_question_to_player(conn)

        elif request['action'] == "answer" and self.game_state == GameState.ASKING_QUESTION:
            player_answer = request.get('answer').lower()
            correct_answer = self.question['correct_answer'].lower()
            logging.info(f"Player {player.name} answered with {player_answer}")
            
            if player_answer in ['true', 'false']:
                if player_answer == correct_answer:
                    player.score += 1
                    answer_feedback = "Correct!"
                else:
                    answer_feedback = "Incorrect!"
                
                response_message = {
                    "action": "answer_feedback",
                    "message": answer_feedback,
                    "score": player.score
                }
                Message.send(conn, response_message) 
                player.answered = True
            else:
                answer_feedback = "Invalid answer format. Please reply with 'True' or 'False'."
                response_message = {
                    "action": "answer_feedback",
                    "message": answer_feedback
                }
                Message.send(conn, response_message)

            if all(player.answered for player in self.clients.values()):
                logging.info(f'All players have answered')
                self.notify_scores() 
                self.reset_for_next_question()
                self.send_question()
                
    def notify_all(self, message):
        for conn, player in self.clients.items():
            logging.debug(f'Notify all being sent: {message}')
            Message.send(conn, message)
        logging.info(f'Notification sent to all players.')
        
    def notify_scores(self):
        scores = {
            "action": "score_update",
            "scores": {player.name: player.score for player in self.clients.values()}
        }
        logging.debug(f"Scores being sent: {scores}") 
        self.notify_all(scores)
        logging.info("Scores update sent.")

    
    def reset_for_next_question(self):
        self.question = None
        for conn, player in self.clients.items():
            player.answered = False
        logging.info(f'Game state reset for next round.')
        
    def fetch_question(self):
        if not self.question_queue:
            response = requests.get(API_URL)
            if response.status_code == 200:
                self.question_queue = response.json().get('results', [])
                logging.info(f'Fetched {len(self.question_queue)} questions from the API.')
            else:
                logging.error('Failed to fetch questions from API.')
        return self.question_queue.pop(0)
                
    def send_question(self):
        logging.info(f'Preparing to send question...')
        while self.question is None:
            self.question = self.fetch_question()
            if self.question is None:
                logging.warning("Failed to fetch question. Retrying in 2 seconds...")
                time.sleep(2)
                
        if self.question:
            question_message = {
                "action": "question",
                "question": self.question['question']
            }
            self.notify_all(question_message)
            logging.info(f'Question sent to all players.')
        else:
            logging.warning(f'No question available to send.')
    
    def send_question_to_player(self, conn):
        question_message = {
            "action": "question",
            "question": self.question['question']
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
