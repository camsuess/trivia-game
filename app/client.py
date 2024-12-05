import socket
import selectors
import argparse
import json
import struct
import logging
import sys
import threading

LOG_FILE = 'client.log'

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s - %(message)s',
                    filename=LOG_FILE,
                    filemode='a')

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.server_address = (host, port)
        self.client_socket = self.create_client_socket()
        self.recv_buffer = b""
        self.send_buffer = b""
        self.running = True
        self.lock = threading.Lock()

    def create_client_socket(self):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(self.server_address)
            client_socket.setblocking(False)
            self.sel.register(client_socket, selectors.EVENT_READ | selectors.EVENT_WRITE, self.handle_server)
            logging.info(f"Connected to server at {self.server_address}")
            return client_socket
        except Exception as e:
            logging.error(f"Failed to connect to server at {self.server_address}: {e}")
            sys.exit(1)

    def send_message(self, message):
        try:
            message_data = json.dumps(message).encode('utf-8')
            message_length = struct.pack('>I', len(message_data))
            with self.lock:
                self.send_buffer += message_length + message_data
            logging.debug(f"Queued message to server: {message}")
        except Exception as e:
            logging.error(f"Error queuing message to server: {e}")

    def receive_message(self):
        try:
            data = self.client_socket.recv(1024)
            if not data:
                logging.info("Server closed the connection.")
                print("Server disconnected.")
                self.running = False
                return None
            self.recv_buffer += data

            messages = []
            while True:
                if len(self.recv_buffer) < 4:
                    break  # Not enough data for message length
                message_length = struct.unpack('>I', self.recv_buffer[:4])[0]
                if len(self.recv_buffer) < 4 + message_length:
                    break  # Not enough data for the complete message
                message_data = self.recv_buffer[4:4 + message_length]
                self.recv_buffer = self.recv_buffer[4 + message_length:]
                message = json.loads(message_data.decode('utf-8'))
                logging.debug(f"Received message from server: {message}")
                messages.append(message)
            return messages
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return []
        except Exception as e:
            logging.error(f"Error receiving message: {e}")
            self.running = False
            return []

    def handle_server(self, sock, mask):
        if mask & selectors.EVENT_READ:
            messages = self.receive_message()
            if messages is not None:
                for message in messages:
                    self.process_server_message(message)
            else:
                self.running = False
        if mask & selectors.EVENT_WRITE:
            with self.lock:
                if self.send_buffer:
                    try:
                        sent = self.client_socket.send(self.send_buffer)
                        logging.debug(f"Sent {sent} bytes to server")
                        self.send_buffer = self.send_buffer[sent:]
                    except BlockingIOError:
                        logging.debug("Write not ready.")
                    except Exception as e:
                        logging.error(f"Error sending message to server: {e}")
                        self.running = False

    def process_server_message(self, message):
        action = message.get("action")
        if not action:
            logging.warning("Received message without 'action' field.")
            print("Received an invalid message from the server.")
            return

        logging.info(f"Processing action '{action}' from server")

        if action == "set_name":
            self.handle_set_name(message)
        elif action == "game_menu":
            self.handle_game_menu(message)
        elif action == "game_created":
            print(message.get("message", "Game created successfully."))
        elif action == "game_joined":
            print(message.get("message", "Joined game successfully."))
        elif action == "player_joined":
            print(f"Player '{message.get('player')}' has joined the game.")
        elif action == "game_started":
            print(message.get("message", "The game has started!"))
        elif action == "question":
            self.handle_question(message)
        elif action == "answer_feedback":
            print(f"{message.get('message')} Your current score: {message.get('score')}\n")
        elif action == "score_update":
            print(f"Current Scoreboard:\n{message.get('scores')}\n")
        elif action == "game_over":
            print(message.get("message", "Game over!"))
            print("Returning to the main menu...")
            self.send_message({"action": "game_menu"})
        elif action == "player_left":
            print(f"Player '{message.get('player')}' has left the game.")
        elif action == "error":
            print(f"\nError: {message.get('message')}")
        elif action == "server_shutdown":
            print(message.get("message", "Server is shutting down."))
            self.running = False
        else:
            logging.warning(f"Unknown action '{action}' received from server.")

    def handle_set_name(self, message):
        username = input(message.get("message", "Enter your username: ")).strip()
        while not username:
            print("Username cannot be blank.")
            username = input(message.get("message", "Enter your username: ")).strip()
        self.send_message({"action": "set_name", "name": username})

    def handle_game_menu(self, message):
        options = message.get("options", [])
        if not options:
            print("No options available. Returning to previous menu.")
            return
        print("\nGame Menu:")
        for option in options:
            print(option)
        choice = input("Choose an option: ").strip()
        if choice == "1":
            self.send_message({"action": "join_game"})
        elif choice == "2":
            self.send_message({"action": "create_game"})
        elif choice == "3":
            self.send_message({"action": "disconnect"})
        else:
            print("Invalid choice. Please select a valid option.")
            self.handle_game_menu(message)  # Wait for valid input

    def handle_question(self, message):
        question = message.get("question", "No question provided.")
        options = message.get("options", [])
        print(f"\nQuestion: {question}")
        print("Options: " + ", ".join(options))
        self.send_answer()

    def send_answer(self):
        answer = input("Your answer (True/False): ").strip().lower()
        while answer not in ["true", "false", "exit"]:
            print("Invalid answer. Please respond with 'True' or 'False'.\nTo exit back to the main menu enter 'Exit'.")
            answer = input("Your answer (True/False): ").strip().lower()
        if answer == 'exit':
            self.send_message({"action": "exit_room"})
        else:
            self.send_message({"action": "answer", "answer": answer})

    def start(self):
        try:
            while self.running:
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            print("\nInterrupt received. Shutting down...")
            logging.info("KeyboardInterrupt received. Shutting down client.")
            self.send_message({"action": "disconnect"})
            # Attempt to flush send_buffer
            with self.lock:
                try:
                    while self.send_buffer:
                        sent = self.client_socket.send(self.send_buffer)
                        self.send_buffer = self.send_buffer[sent:]
                except Exception as e:
                    logging.error(f"Error flushing send_buffer during shutdown: {e}")
            self.sel.unregister(self.client_socket)
            self.client_socket.close()
            sys.exit(0)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print("An unexpected error occurred. Exiting...")
            self.sel.unregister(self.client_socket)
            self.client_socket.close()
            sys.exit(1)
        finally:
            self.sel.close()

def parse_args():
    parser = argparse.ArgumentParser(description="Trivia Game Client")
    parser.add_argument("-i", "--ip", default="127.0.0.1", help="Server IP")
    parser.add_argument("-p", "--port", type=int, required=True, help="Server Port")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    client = GameClient(args.ip, args.port)
    client.start()
