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
    QUESTION_SETUP = "question_setup"
    ASKING_QUESTION = "asking"
    WAITING_FOR_NEXT_ROUND = "waiting_for_next_round"
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
            self.disconnect(player)
        
        if request['action'] == "set_name":
            self.set_name(request, player)
        
        if request['action'] == "answer" and self.game_state == GameState.ASKING_QUESTION:
            self.receive_answer(conn, request, player)
            if all(player.answered for player in self.clients.values()):
                self.next_phase()
                self.game_state = GameState.WAITING_FOR_NEXT_ROUND
    
    def next_phase(self):
        if self.game_state == GameState.WAITING:
            self.prepare_question()
        elif self.game_state == GameState.QUESTION_SETUP:
            self.broadcast_question()
        elif self.game_state == GameState.ASKING_QUESTION:
            if all(player.answered for conn, player in self.clients.items()):
                self.complete_round()
        elif self.game_state == GameState.WAITING_FOR_NEXT_ROUND:
            self.reset_for_next_question()
            self.prepare_question()
            
    def prepare_question(self):
        if not self.question:
            self.question = self.fetch_question()
        if self.question:
            logging.debug(f"Question prepared: {self.question['question']}")
            self.game_state = GameState.QUESTION_SETUP
            self.next_phase()
        else:
            logging.debug("No question was fetched.")    
        
    def broadcast_question(self):
        if self.question and self.game_state == GameState.QUESTION_SETUP:
            question_message = {
                "action": "question",
                "question": self.question['question']
            }
            self.notify_all(question_message)
            logging.info("Question broadcasted to all players.")
            self.game_state = GameState.ASKING_QUESTION
        
    def complete_round(self):
        self.notify_scores()
        self.game_state = GameState.WAITING_FOR_NEXT_ROUND
        self.next_phase()
                
    def notify_all(self, message):
        for conn, player in self.clients.items():
            logging.debug(f'Notify all being sent: {message}')
            Message.send(conn, message)
        logging.info(f'Notification sent to all players.')
        
    def notify_scores(self):
        scores = {
            "action": "score_update",
            "scores": {player.name: player.score for conn, player in self.clients.items()}
        }
        logging.debug(f"Scores being sent: {scores}") 
        self.notify_all(scores)
        logging.info("Scores update sent.")

    
    def reset_for_next_question(self):
        self.question = None
        for conn, player in self.clients.items():
            player.answered = False
        logging.info('Game state reset for next round.')
        self.game_state = GameState.WAITING
        self.next_phase()
        
    def fetch_question(self):
        if not self.question_queue:
            response = requests.get(API_URL)
            if response.status_code == 200:
                self.question_queue = response.json().get('results', [])
                logging.info(f'Fetched {len(self.question_queue)} questions from the API.')
            else:
                logging.error('Failed to fetch questions from API.')
        return self.question_queue.pop(0)
    
    def disconnect(self, conn, player):
        logging.info(f'\nPlayer {player.name} disconnected from the server.\n')
        self.sel.unregister(conn)
        conn.close()
        self.clients.pop(conn, None)
        
        if all(player.answered for conn, player in self.clients.items()):
            logging.info(f'All players have answered')
            self.notify_scores() 
            self.reset_for_next_question()
            self.broadcast_question()
            
    def set_name(self, request, player):
        player.name = request.get('name')
        logging.info(f"Player {player.name} connected from {player.address}.")
        if all(player.name for conn, player in self.clients.items()):
            self.game_state = GameState.QUESTION_SETUP
            self.next_phase()
    
    def receive_answer(self, conn, request, player):
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