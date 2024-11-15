from message import Message

import logging
import requests
import socket
import selectors
import argparse
import uuid

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

class GameRoom:
    def __init__(self, room_id, room_type, creator, is_private=False):
        self.room_id = room_id
        self.room_type = room_type  # public or private game room
        self.creator = creator      # player who created the game room
        self.players = [creator]    # list of players
        self.is_private = is_private
        self.in_progress = False
        self.max_players = 5 if room_type == 'public' else 2 # min/max players for game room
        self.game_state = GameState.WAITING
        self.question_queue = []
        self.current_question = None

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = {}
        self.rooms = {}
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
        
        elif request['action'] == "set_name":
            self.set_name(request, player)
        
        elif request['action'] == "game_menu":
            self.show_menu(conn, player)
            
        elif request['action'] == "join_game":
            self.join_game(conn, player, request)
        
        elif request['action'] == "create_game":
            self.create_game(conn, player, request)
        
        elif request['action'] == "start_game":
            self.start_game(conn, player, request)
        
        elif request['action'] == "answer":
            self.process_answer(conn, player, request)
    
    def show_menu(self, conn, player):
        menu = {
            "action": "game_menu",
            "options": [
                "1. Join a current public game",
                "2. Start your own public game",
                "3. Start a private game",
                "4. Join a private game"
            ]
        }
        Message.send(conn, menu)   
        
    def create_game(self, conn, player, request):
        room_id = str(uuid.uuid4())[:8]
        room_type = request.get('room_type', 'public')
        is_private = room_type == 'private'
        room = GameRoom(room_id, room_type, player, is_private)
        self.rooms[room_id] = room
        player.current_room = room_id
        response = {
            "action": "game_created",
            "room_id": room_id,
            "message": f"Game created with ID: {room_id}. Waiting for players to join..."
        }
        Message.send(conn, response)
        logging.info(f'Game room {room_id} created by {player.name}')
    
    def join_game(self, conn, player, request):
        if request.get('room_type') == 'public':
            room = self.find_available_public_game()
            if room:
                self.add_player_to_room(conn, player,room)
                return
            else:
                response = {
                    "action": "error",
                    "message": "No avaiable public games to join."
                }
                Message.send(conn, response)
        else:
            room_id = request.get('room_id')
            room = self.rooms.get(room_id)
            if room and room.is_private and len(room.players) < room.max_players:
                self.add_player_to_room(conn, player, room)
            else:
                response = {
                    "action": "error",
                    "message": "Failed to join private game. It might be full or does not exist anymore."
                }
                Message.send(conn, response)
            
    def find_available_public_game(self):
        for room in self.rooms.values():
            if room.room_type == 'public' and not room.is_private and len(room.players) < room.max_players and not room.in_progress:
                return room
        return None
    
    def add_player_to_room(self, conn, player, room):
        room.players.append(player)
        player.current_room = room.room_id
        response = {
            "action": "game_joined",
            "room_id": room.room_id,
            "message": f"Joined game {room.room_id}. Waiting for game to start."
        }
        Message.send(conn, response)
        logging.info(f"Player {player.name} joined game {room.room_id}.")
        self.notify_room(room, {
            "action": "player_joined",
            "player": player.name
        })
        
    def send_name_prompt(self, conn):
        prompt = {
            "action": "set_name",
            "message": "Please enter your username: "
        }
        Message.send(conn, prompt)
        
    def start_game(self, conn, player, request):
        room_id = player.current_room
        room = self.rooms.get(room_id)
        if room and room.creator == player:
            if len(room.players) >= 2:
                room.in_progress = True
                room.game_state = GameState.QUESTION_SETUP
                self.fetch_question(room)
                self.broadcast_to_room(room, {
                    "action": "game_started",
                    "message": "Game is starting!"
                })
                self.broadcast_question(room)
            else:
                response = {
                    "action": "error",
                    "message": "Not enough players to start the game."
                }
                Message.send(conn, response)
        else:
            response = {
                "action": "error",
                "message": "Only the game creator can start the game."
            }
            Message.send(conn, response)
    
    def process_answer(self, conn, player, request):
        room_id = player.current_room
        room = self.rooms.get(room_id)
        if room and room.game_state == GameState.ASKING_QUESTION:
            self.receive_answer(conn, request, player)
            if all(p.answered for p in room.players):
                self.complete_round(room)
    
    def fetch_question(self, room):
        if not room.question_queue:
            response = requests.get(API_URL)
            if response.status_code == 200:
                room.question_queue = response.json().get('results', [])
                logging.info(f'Fetched {len(room.question_queue)} questions for room {room.room_id}')
            else:
                logging.error(f'Failed to fetch questions for room {room.room_id}')
                return
        room.current_question = room.question_queue.pop(0)
        room.game_state = GameState.ASKING_QUESTION
        logging.debug(f'Question fetched for room {room.room_id}: {room.current_question}')
    
    def broadcast_question(self, room):
        if room.current_question and room.game_state == GameState.ASKING_QUESTION:
            question_message = {
                "action": "question",
                "question": room.current_question['question']
            }
            self.broadcast_to_room(room, question_message)
            logging.info(f"Question broadcasted to room {room.room_id}")
        
    def broadcast_to_room(self, room, message):
        for player in room.players:
            Message.send(player.conn, message)
            
    def notify_room(self, room, message):
        self.broadcast_to_room(room, message)
    
    def disconnect(self, conn, player):
        logging.info(f'Player {player.name} disconnected from the server.')
        self.sel.unregister(conn)
        conn.close()
        self.clients.pop(conn, None)
        
        room_id = player.current_room
        if room_id:
            room = self.rooms.get(room_id)
            if room:
                room.players.remove(player)
                self.notify_room(room, {
                    "action": "player_left",
                    "player": player.name
                })
                logging.info(f"Player {player.name} left game {room_id}")
                
                # remove room if empty
                if not room.players:
                    del self.rooms[room_id]
                    logging.info(f"Game room {room_id} has been removed as it became empty.")
                else:
                    # if creator leaves assign new creator for the game room
                    if room.creator == player:
                        room.creator = room.players[0]
                        self.notify_room(room, {
                            "action": "new_creator",
                            "player": room.creator.name
                        })
                        logging.info(f"New creator for room {room_id} is {room.creator.name}")

            
    def set_name(self, request, player):
        player.name = request.get('name')
        logging.info(f"Player {player.name} connected from {player.address}.")
        self.show_menu(player.conn, player)
    
    def next_phase(self, room):
        if room.game_state == GameState.WAITING:
            self.fetch_question(room)
        elif room.game_state == GameState.QUESTION_SETUP:
            self.broadcast_question(room)
        elif room.game_state == GameState.ASKING_QUESTION:
            if all(player.answered for player in room.players):
                self.complete_round(room)
        elif room.game_state == GameState.WAITING_FOR_NEXT_ROUND:
            self.reset_for_next_question(room)
            self.fetch_question(room)
    
    def receive_answer(self, conn, request, player):
        room_id = player.current_room
        room = self.rooms.get(room_id)
        if not room or room.game_state != GameState.ASKING_QUESTION:
            return
        
        player_answer = request.get('answer').lower()
        correct_answer = room.current_question['correct_answer'].lower()
        logging.info(f"Player {player.name} answered with {player_answer} in room {room_id}")
        
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
        
        if all(player.answered for player in room.players):
            self.complete_round(room)
        
        
    def complete_round(self, room):
        self.notify_scores(room)
        # check for winners and handle it
        winners = [player for player in room.players if player.score >= 10]
        if len(winners) == 1:
            self.end_game(room, winner=winners[0])
        elif len(winners) > 1:
            self.process_tie_breaker(room)
        else:
            room.game_state = GameState.WAITING_FOR_NEXT_ROUND
            self.next_phase(room)
    
    def process_tie_breaker(self, room):
        room.game_state = GameState.ASKING_QUESTION
        message = {
            "action": "tie_breaker",
            "message": "It's a tie! Continuing the game until one player leads by one point..."
        }
        self.broadcast_to_room(room, message)
        logging.info(f"Tie breaker initiated in room {room.room_id}")
        self.prepare_question(room)
        self.broadcast_question(room)
    
    def notify_scores(self, room):
        scores = {
            "action": "score_update",
            "scores": {player.name: player.score for player in room.players}
        }
        self.broadcast_to_room(room, scores)
        logging.info(f'Scores update sent to room {room.room_id}')
        
    def reset_for_next_question(self, room):
        room.current_question = None
        for player in room.players:
            player.answered = False
        room.game_state = GameState.WAITING
        logging.info(f'Game state reset for next round in room {room.room_id}.')

    def start(self):
        try:
            while True:
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
                # handle each game room
                for room_id, room in list(self.rooms.items()):
                    if room.game_state not in [GameState.FINISHED]:
                        self.next_phase(room)
        except KeyboardInterrupt:
            logging.info("Server shutting down...")
        finally:
            self.sel.close()
    
    def end_game(self, room, winner):
        message = {
            "action": "game_over",
            "message": f"Game over! The winner is {winner.name} with {winner.score} points."
        }
        self.broadcast_to_room(room, message)
        room.game_state = GameState.FINISHED
        logging.info(f"Game in room {room.room_id} ended. Winner: {winner.name}")
        # remove game after completion
        del self.rooms[room.room_id]
        logging.info(f"Game room {room.room_id} has been removed after game completion.")

    
def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Server', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, default='0.0.0.0', help='The IP address to bind the server')
    parser.add_argument('-p', '--port', type=int, required=True, help='The port to bind the server')
    parser.add_argument('-h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    server = GameServer(host=args.ip, port=args.port)
    server.start()