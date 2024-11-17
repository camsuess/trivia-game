import socket
import selectors
import argparse
import logging
import threading
import time
from message import Message

logging.basicConfig(level=logging.DEBUG, 
                    format='%(levelname)s - %(message)s',
                    filename='client.log'
                    )

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.client_socket = self.create_client_socket()
        self.username_set = False
        self.current_room = False
        self.running = True
        self.lock = threading.Lock()
        self.show_menu_flag = False
        self.prompt_start_flag = False
        self.waiting_for_answer = False
        self.current_question = None
        self.show_answer_feedback = False
        self.show_score_update = False
        self.show_game_joined_message = False
        self.game_over_flag = False
        self.username_prompt = ""
        self.menu_options = []
        self.game_created_message = ""
        self.game_joined_message = ""
        self.answer_feedback = ""
        self.current_score = 0
        self.scores = {}
        self.action_event = threading.Event()
        
    
    def create_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        client_socket.setblocking(False)
        self.sel.register(client_socket, selectors.EVENT_READ, self.read_response)
        return client_socket
    
    def read_response(self, sock, mask):
        try:
            message = Message()
            message.read(sock)
            if message.request:
                request = message.request
                action = request.get('action')
                logging.debug(f"Received request: {request}")

                if action == "set_name":
                    with self.lock:
                        self.username_prompt = request.get('message')
                        self.username_set = False
                    logging.debug("Set username_prompt and username_set flag")
                    self.action_event.set()
                elif action == "game_menu":
                    with self.lock:
                        self.menu_options = request.get('options')
                        self.show_menu_flag = True
                    logging.debug("Set menu_options and show_menu_flag")
                    self.action_event.set()
                elif action == "game_created":
                    with self.lock:
                        self.game_created_message = request.get('message')
                        self.current_room = request.get('room_id')
                        self.prompt_start_flag = True
                    logging.debug("Set game_created_message and prompt_start_flag")
                    self.action_event.set()
                elif action == "game_joined":
                    with self.lock:
                        self.game_joined_message = request.get('message')
                        self.current_room = request.get('room_id')
                        self.show_game_joined_message = True
                    logging.debug("Set game_joined_message and show_game_joined_message")
                    self.action_event.set()
                elif action == "player_joined":
                    player_name = request.get('player')
                    print(f"Player '{player_name}' has joined the game.")
                elif action == "game_started":
                    game_started_message = request.get('message')
                    print(game_started_message)
                    print("Game has started! Get ready for the first question.")
                elif action == "question":
                    with self.lock:
                        self.current_question = request.get('question')
                        self.waiting_for_answer = True
                    logging.debug("Set current_question and waiting_for_answer flag")
                    self.action_event.set()
                elif action == "answer_feedback":
                    with self.lock:
                        self.answer_feedback = request.get('message')
                        self.current_score = request.get('score')
                        self.show_answer_feedback = True
                    logging.debug("Set answer_feedback and show_answer_feedback")
                    self.action_event.set()
                elif action == "score_update":
                    with self.lock:
                        self.scores = request.get('scores', {})
                        self.show_score_update = True
                    logging.debug("Set scores and show_score_update")
                    self.action_event.set()
                elif action == "game_over":
                    with self.lock:
                        self.game_over_message = request.get('message')
                        self.game_over_flag = True
                    logging.debug("Set game_over_message and game_over_flag")
                    self.action_event.set()
                elif action == "error":
                    error_message = request.get('message')
                    print(f"\nError: {error_message}")
        except Exception as e:
            logging.error(f"Error in read_response{e}")
            self.running = False
            self.notify_disconnect()
                

    def prompt_for_username(self):
        username = input(self.username_prompt)
        while not username.strip():
            print("Username cannot be blank.", flush=True)
            username = input(self.username_prompt)
        response_message = {
            "action": "set_name",
            "name": username.strip()
        }
        Message.send(self.client_socket, response_message)
        self.username_set = True

        
    def display_game_menu(self):
        print("\n--- Game Menu ---")
        for option in self.menu_options:
            print(option, flush=True)
        choice = input("Select an option (1-4): ")
        if choice == '1':
            self.join_public_game()
        elif choice == '2':
            self.create_public_game()
        elif choice == '3':
            self.create_private_game()
        elif choice == '4':
            self.join_private_game()
        else:
            print("Invalid choice. Please select again.")
            return  # Keep the flag true to prompt again
        self.show_menu_flag = False  # Reset the flag

            
    def join_public_game(self):
        response_message = {
            "action": "join_game",
            "room_type": "public"
        }
        Message.send(self.client_socket, response_message)
        print("Joining the first available public game...")
    
    def create_public_game(self):
        response_message = {
            "action": "create_game",
            "room_type": "public"
        }
        Message.send(self.client_socket, response_message)
        
    def create_private_game(self):
        response_message = {
            "action": "create_game",
            "room_type": "private"
        }
        Message.send(self.client_socket, response_message)
        
    def join_private_game(self):
        room_id = input("Enter the Room ID of the private game you want to join: ").strip()
        if not room_id:
            print("Room ID cannot be empty.")
            self.join_private_game()
            return
        response_message = {
            "action": "join_game",
            "room_id": room_id
        }
        Message.send(self.client_socket, response_message)

    def prompt_start_game(self):
        print(self.game_created_message)
        choice = input("Do you want to start the game now? (yes/no): ").strip().lower()
        if choice in ['yes', 'y']:
            response_message = {
                "action": "start_game"
            }
            Message.send(self.client_socket, response_message)
        elif choice in ['no', 'n']:
            print("Waiting for other players to join...")
        else:
            print("Invalid choice. Please enter 'yes' or 'no'.")
            return  # keep the flag true to prompt again
        self.prompt_start_flag = False  # reset the flag
        

    def get_answer(self):
        logging.debug("Entering get_answer")
        print(f"\nQuestion: {self.current_question}", flush=True)
        answer = input("Your answer (true/false): ").strip().lower()
        while answer not in ['true', 'false']:
            print("Invalid answer format. Please reply with 'True' or 'False'.", flush=True)
            answer = input("Your answer (true/false): ").strip().lower()
        answer_message = {
            "action": "answer",
            "answer": answer
        }
        Message.send(self.client_socket, answer_message)
        with self.lock:
            self.waiting_for_answer = False  # Reset the flag
        logging.debug("Exiting get_answer and reset waiting_for_answer flag")


    
    def display_answer_feedback(self):
        print(f"\n{self.answer_feedback}")
        if self.current_score is not None:
            print(f"Your current score: {self.current_score}\n")
        with self.lock:
            self.show_answer_feedback = False  # Reset the flag
        logging.debug("Exiting display_answer_feedback and reset show_answer_feedback flag")
        

    def display_score_update(self):
        print("\n--- Current Game Scores ---")
        for player, score in self.scores.items():
            print(f"{player}: {score}")
        print("---------------------------\n")
        with self.lock:
            self.show_score_update = False  # Reset the flag
        logging.debug("Exiting display_score_update and reset show_score_update flag")

        

    def handle_game_over(self):
        print(f"\n{self.game_over_message}")
        play_again = input("Do you want to play again? (yes/no): ").strip().lower()
        if play_again in ['yes', 'y']:
            self.reset_game()
        else:
            self.notify_disconnect()
        self.game_over_flag = False  # Reset the flag


    def reset_game(self):
        self.current_room = None
        response_message = {
            "action": "set_name",
            "name": None
        }
        self.show_game_menu({
            "action": "game_menu",
            "options": [
                "1. Join a current public game",
                "2. Start your own public game",
                "3. Start a private game"
            ]
        })
        
        
    def listen_for_messages(self):
        while self.running:
            try:
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
            except Exception as e:
                logging.error(f"Error in listen_for_messages: {e}")
                self.running = False
                self.notify_disconnect()
                break
    
    def start(self):
        listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()

        try:
            while self.running:
                self.action_event.wait()
                self.action_event.clear()
                action_to_take = None

                with self.lock:
                    if not self.username_set and self.username_prompt:
                        action_to_take = 'prompt_for_username'
                    elif self.show_menu_flag:
                        action_to_take = 'display_game_menu'
                    elif self.prompt_start_flag:
                        action_to_take = 'prompt_start_game'
                    elif self.waiting_for_answer:
                        action_to_take = 'get_answer'
                    elif self.show_game_joined_message:
                        action_to_take = 'show_game_joined_message'
                    elif self.show_answer_feedback:
                        action_to_take = 'display_answer_feedback'
                    elif self.show_score_update:
                        action_to_take = 'display_score_update'
                    elif self.game_over_flag:
                        action_to_take = 'handle_game_over'

                logging.debug(f"Main loop action: {action_to_take}")

                # Perform the action without holding the lock
                if action_to_take == 'prompt_for_username':
                    self.prompt_for_username()
                elif action_to_take == 'display_game_menu':
                    self.display_game_menu()
                elif action_to_take == 'prompt_start_game':
                    self.prompt_start_game()
                elif action_to_take == 'get_answer':
                    self.get_answer()
                elif action_to_take == 'show_game_joined_message':
                    with self.lock:
                        print(self.game_joined_message)
                        print("Waiting for the game to start...")
                        self.show_game_joined_message = False
                elif action_to_take == 'display_answer_feedback':
                    self.display_answer_feedback()
                elif action_to_take == 'display_score_update':
                    self.display_score_update()
                elif action_to_take == 'handle_game_over':
                    self.handle_game_over()
        except KeyboardInterrupt:
            logging.info("\nClient shutting down.")
            self.running = False
            self.notify_disconnect()
        finally:
            self.close()



    def close(self):
        self.sel.unregister(self.client_socket)
        self.client_socket.close()
        exit(0)
        
    def notify_disconnect(self):
        message = {
            "action": "disconnect"
        }
        Message.send(self.client_socket, message)
        print("Disconnected from the server.")
        self.close()
        

def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Client', add_help=False)
    parser.add_argument('-i', '--ip', type=str, default='127.0.0.1', help='Server IP')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server Port')
    parser.add_argument('-h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    client = GameClient(host=args.ip, port=args.port)
    client.start()