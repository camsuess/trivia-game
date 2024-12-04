import logging
import socket
import selectors
import argparse
import json
import struct
import requests
import sys
import uuid

API_URL = 'https://opentdb.com/api.php?amount=50&type=boolean'
LOG_FILE = 'server.log'
DEFAULT_MAX_PLAYERS_PER_ROOM = 3

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s - %(message)s',
                    filename=LOG_FILE,
                    filemode='a')


class Player:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.name = None
        self.recv_buffer = b""
        self.send_buffer = b""
        self.events = selectors.EVENT_READ
        self.score = 0
        self.answered = False


class GameRoom:
    def __init__(self, room_id, max_players=DEFAULT_MAX_PLAYERS_PER_ROOM):
        self.room_id = room_id
        self.players = []
        self.in_progress = False
        self.current_question = None
        self.questions = []
        self.current_question_index = 0
        self.max_players = max_players

    def is_full(self):
        return len(self.players) >= self.max_players


class GameServer:
    def __init__(self, host, port, max_players_per_room):
        self.sel = selectors.DefaultSelector()
        self.clients = {}
        self.rooms = {}
        self.server_socket = self.create_server_socket(host, port)
        self.max_players_per_room = max_players_per_room

    def create_server_socket(self, host, port):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        server_socket.setblocking(False)
        self.sel.register(server_socket, selectors.EVENT_READ, self.accept_connection)
        logging.info(f"Server started on {host}:{port}")
        return server_socket

    def accept_connection(self, server_socket, mask):
        conn, addr = server_socket.accept()
        conn.setblocking(False)
        player = Player(conn, addr)
        self.clients[conn] = player
        self.sel.register(conn, selectors.EVENT_READ | selectors.EVENT_WRITE, self.handle_client)
        logging.info(f"New connection from {addr}")
        self.send_message(player, {"action": "set_name", "message": "Enter your username: "})

    def handle_client(self, conn, mask):
        player = self.clients.get(conn)
        if not player:
            logging.warning(f"Handle client called for unknown connection {conn}")
            return

        if mask & selectors.EVENT_READ:
            self.receive_message(player)
        if mask & selectors.EVENT_WRITE:
            self.send_buffered_messages(player)

    def send_message(self, player, message):
        try:
            message_json = json.dumps(message).encode('utf-8')
            message_length = struct.pack('>I', len(message_json))
            player.send_buffer += message_length + message_json

            if not player.events & selectors.EVENT_WRITE:
                player.events |= selectors.EVENT_WRITE
                self.sel.modify(player.conn, player.events, self.handle_client)
            logging.debug(f"Queued message to {player.name}: {message}")
        except Exception as e:
            logging.error(f"Error queuing message to {player.addr}: {e}")
            self.disconnect(player)

    def receive_message(self, player):
        try:
            data = player.conn.recv(1024)
            if not data:
                self.disconnect(player)
                return
            player.recv_buffer += data

            while True:
                if len(player.recv_buffer) < 4:
                    break  # Not enough data for message length
                message_length = struct.unpack('>I', player.recv_buffer[:4])[0]
                if len(player.recv_buffer) < 4 + message_length:
                    break  # Not enough data for the complete message
                message_data = player.recv_buffer[4:4 + message_length]
                player.recv_buffer = player.recv_buffer[4 + message_length:]
                message = json.loads(message_data.decode('utf-8'))
                self.process_message(player, message)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error from {player.addr}: {e}")
            self.send_message(player, {"action": "error", "message": "Invalid message format."})
        except Exception as e:
            logging.error(f"Error receiving message from {player.addr}: {e}")
            self.disconnect(player)

    def send_buffered_messages(self, player):
        try:
            if player.send_buffer:
                sent = player.conn.send(player.send_buffer)
                player.send_buffer = player.send_buffer[sent:]
                if not player.send_buffer:  # All data sent successfully!
                    player.events &= ~selectors.EVENT_WRITE
                    self.sel.modify(player.conn, player.events, self.handle_client)
        except BlockingIOError:
            logging.debug(f"Write not ready for player {player.name}")
        except Exception as e:
            logging.error(f"Error sending message to {player.addr}: {e}")
            self.disconnect(player)

    def process_message(self, player, message):
        action = message.get("action")
        if not action:
            logging.warning(f"Received message without 'action' from {player.addr}")
            self.send_message(player, {"action": "error", "message": "Missing 'action' in message."})
            return

        logging.info(f"Processing action '{action}' from player '{player.name}'")

        if action == "set_name":
            self.handle_set_name(player, message)
        elif action == "create_game":
            self.create_game_room(player)
        elif action == "join_game":
            self.join_game_room(player)
        elif action == "answer":
            self.process_answer(player, message.get("answer"))
        elif action == "disconnect":
            self.disconnect(player)
        elif action == "game_menu":
            self.send_message(player, {"action": "game_menu", "options": ["1. Join a game", "2. Create a game", "3. Exit"]})
        else:
            logging.warning(f"Unknown action '{action}' from player '{player.name}'")
            self.send_message(player, {"action": "error", "message": f"Unknown action '{action}'."})

    def handle_set_name(self, player, message):
        name = message.get("name")
        if not name:
            self.send_message(player, {"action": "error", "message": "Username cannot be empty."})
            return
        player.name = name.strip()
        logging.info(f"Player '{player.name}' connected from {player.addr}")
        self.send_message(player, {"action": "game_menu", "options": ["1. Join a game", "2. Create a game", "3. Exit"]})

    def create_game_room(self, player):
        existing_room = self.get_player_room(player)
        if existing_room:
            self.send_message(player, {"action": "error", "message": "You are already in a game room."})
            return

        room_id = str(uuid.uuid4())[:8]
        room = GameRoom(room_id, max_players=self.max_players_per_room)
        room.players.append(player)
        self.rooms[room_id] = room
        self.send_message(player, {"action": "game_created", "room_id": room_id,
                                   "message": f"Room {room_id} created. Waiting for players to join."})
        logging.info(f"Game room {room_id} created by '{player.name}'.")

    def join_game_room(self, player):
        # Check if player is already in a room first
        existing_room = self.get_player_room(player)
        if existing_room:
            self.send_message(player, {"action": "error", "message": "You are already in a game room."})
            return

        for room in self.rooms.values():
            if not room.in_progress and not room.is_full():
                room.players.append(player)
                self.send_message(player, {"action": "game_joined", "room_id": room.room_id,
                                           "message": f"Joined room {room.room_id}. Waiting for the game to start."})
                self.notify_room(room, {"action": "player_joined", "player": player.name})
                logging.info(f"Player '{player.name}' joined room {room.room_id}")

                if len(room.players) >= DEFAULT_MAX_PLAYERS_PER_ROOM:  # Start game if maximum players are reached
                    self.start_game(room)
                return

        self.send_message(player, {"action": "error", "message": "No available public games to join. Consider creating one."})
        self.send_message(player, {"action": "game_menu", "options": ["1. Join a game", "2. Create a game", "3. Exit"]})

    def start_game(self, room):
        if room.in_progress:
            logging.warning(f"Attempted to start an already in-progress game in room {room.room_id}")
            return

        logging.info(f"Starting game in room {room.room_id} with players: {[p.name for p in room.players]}")
        room.in_progress = True
        # Initialize scores and answered flags
        for player in room.players:
            player.score = 0
            player.answered = False

        self.notify_room(room, {"action": "game_started", "message": "The game has started! Get ready for the first question."})
        self.fetch_and_broadcast_question(room)

    def fetch_questions(self, room):
        try:
            response = requests.get(API_URL)
            if response.status_code == 200:
                questions = response.json().get('results', [])
                if questions:
                    room.questions = questions
                    room.current_question_index = 0
                    logging.info(f"Fetched {len(questions)} questions for room {room.room_id}")
                else:
                    logging.error(f"No questions available from the API for room {room.room_id}.")
                    self.notify_room(room, {"action": "error", "message": "No questions available. Game cannot proceed."})
                    self.end_game_due_to_error(room)
            else:
                logging.error(f"Failed to fetch questions. Status code: {response.status_code} for room {room.room_id}")
                self.notify_room(room, {"action": "error", "message": "Failed to fetch questions. Game cannot proceed."})
                self.end_game_due_to_error(room)
        except Exception as e:
            logging.error(f"Exception while fetching questions for room {room.room_id}: {e}")
            self.notify_room(room, {"action": "error", "message": "An error occurred while fetching questions."})
            self.end_game_due_to_error(room)

    def fetch_and_broadcast_question(self, room):
        if room.current_question_index >= len(room.questions):
            self.fetch_questions(room)
            if not room.questions:
                return

        if room.current_question_index < len(room.questions):
            question = room.questions[room.current_question_index]
            room.current_question = question
            room.current_question_index += 1
            self.notify_room(room, {
                "action": "question",
                "question": question["question"],
                "options": ["True", "False"]
            })
            logging.info(f"Broadcasted question to room {room.room_id}: {question['question']}")

    def process_answer(self, player, answer):
        room = self.get_player_room(player)
        if not room or not room.current_question:
            self.send_message(player, {"action": "error", "message": "No active question to answer."})
            return

        correct_answer = room.current_question["correct_answer"].lower()
        if answer.lower() == correct_answer:
            player.score += 1
            feedback = "Correct!"
        else:
            feedback = "Incorrect!"

        self.send_message(player, {"action": "answer_feedback", "message": feedback, "score": player.score})
        player.answered = True
        logging.info(f"Player '{player.name}' answered '{answer}' in room {room.room_id}. Score: {player.score}")

        if all(p.answered for p in room.players):
            self.end_round(room)

    def end_round(self, room):
        logging.info(f"Ending round in room {room.room_id}")

        scores = {player.name: player.score for player in room.players}
        self.notify_room(room, {"action": "score_update", "scores": scores})

        winners = [p for p in room.players if p.score >= 5]
        if len(winners) == 1:
            winner = winners[0]
            self.notify_room(room, {"action": "game_over", "message": f"{winner.name} wins with {winner.score} points!"})
            room.in_progress = False
            logging.info(f"Game in room {room.room_id} ended. Winner: {winner.name}")
            self.reset_room(room)
        elif len(winners) > 1:
            winner_names = ", ".join([p.name for p in winners])
            self.notify_room(room, {"action": "game_over", "message": f"Game Tied!\n {winner_names} tied with {winners[0].score} points!"})
            room.in_progress = False
            logging.info(f"Game in room {room.room_id} ended. Winners: {winner_names}")
            self.reset_room(room)
        else:
            # Continue the game as normal
            for player in room.players:
                player.answered = False
            self.fetch_and_broadcast_question(room)

    def end_game_due_to_error(self, room):
        room.in_progress = False
        self.reset_room(room)

    def reset_room(self, room):
        for player in room.players:
            player.score = 0
            player.answered = False
        room.players.clear()
        room.questions = []
        room.current_question = None
        room.current_question_index = 0
        del self.rooms[room.room_id]
        logging.info(f"Room {room.room_id} has been reset and removed.")

    def notify_room(self, room, message):
        for player in room.players:
            logging.debug(f"Sending message to '{player.name}' in room {room.room_id}: {message}")
            self.send_message(player, message)

    def disconnect(self, player):
        logging.info(f"Player '{player.name}' disconnected")
        self.sel.unregister(player.conn)
        player.conn.close()
        del self.clients[player.conn]
        room = self.get_player_room(player)
        if room:
            room.players.remove(player)
            self.notify_room(room, {"action": "player_left", "player": player.name})
            logging.info(f"Player '{player.name}' removed from room {room.room_id}")
            if not room.players:
                del self.rooms[room.room_id]
                logging.info(f"Room {room.room_id} deleted as it became empty")
            elif room.in_progress and len(room.players) < 2:
                # Not enough players to continue the game - disconnect and display game menu
                self.notify_room(room, {"action": "error", "message": "Not enough players to continue the game. Game ended."})
                self.notify_room(room, {"action": "game_menu", "options": ["1. Join a game", "2. Create a game", "3. Exit"]})
                self.end_game_due_to_error(room)

    def get_player_room(self, player):
        for room in self.rooms.values():
            if player in room.players:
                return room
        return None

    def shutdown(self):
        logging.info("Server shutting down...")
        shutdown_message = {"action": "server_shutdown", "message": "Server is shutting down."}
        for player in list(self.clients.values()):
            self.send_message(player, shutdown_message)
            self.disconnect(player)
        self.sel.close()
        self.server_socket.close()
        logging.info("Server has been shut down.")

    def start(self):
        try:
            while True:
                events = self.sel.select(timeout=None)
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Initiating shutdown.")
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            self.shutdown()
            sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Trivia Game Server")
    parser.add_argument("-i", "--ip", default="0.0.0.0", help="Server IP")
    parser.add_argument("-p", "--port", type=int, required=True, help="Server Port")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    server = GameServer(args.ip, args.port, args.max)
    server.start()
