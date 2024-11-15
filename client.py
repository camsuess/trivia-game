import socket
import selectors
import argparse
import logging
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
    
    def create_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        client_socket.setblocking(False)
        self.sel.register(client_socket, selectors.EVENT_READ, self.read_response)
        return client_socket
    
    def read_response(self, sock, mask):
        message = Message()
        message.read(sock)
        if message.request:
            request = message.request
            logging.debug(f"Received request: {request}")

            action = request.get('action')

            if action == "set_name":
                self.set_name(request)
            
            elif action == "game_menu":
                self.show_game_menu(request)
            
            elif action == "game_created":
                self.process_game_created(request)
            
            elif action == "game_joined":
                self.process_game_joined(request)
            
            elif action == "player_joined":
                self.process_player_joined(request)
                
            elif action == "player_left":
                self.process_player_left(request)

            elif action == "new_creator":
                self.process_new_creator(request)
            
            elif action == "game_started":
                self.process_game_started(request)
            
            elif action == "question":
                self.process_question(request)
            
            elif action == "answer_feedback":
                self.process_answer_feedback(request)
            
            elif action == "score_update":
                self.process_score_update(request)
            
            elif action == "game_over":
                self.process_game_over(request)
            
            elif action == "tie_breaker":
                self.process_tie_breaker(request)
            
            elif action == "error":
                self.process_error(request)

    def set_name(self, request):
        username = input(request['message'])
        while not username.strip():
            print("Username cannot be blank.")
            username = input(request['message'])
        response_message = {
            "action": "set_name",
            "name": username.strip()
        }
        Message.send(self.client_socket, response_message)
        self.username_set = True
        
    def show_game_menu(self, request):
        print("\n--- Game Menu ---")
        for option in request['options']:
            print(option)
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
            self.show_game_menu(request)
            
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

    def process_game_created(self, request):
        print(request['message'])
        self.current_room = request.get('room_id')
        if self.current_room:
            self.prompt_start_game()

    def prompt_start_game(self):
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
            self.prompt_start_game()
    
    def process_game_joined(self, request):
        print(request['message'])
        self.current_room = request.get('room_id')
        print("Waiting for the game to start...")

    def process_player_joined(self, request):
        player_name = request.get('player')
        print(f"Player '{player_name}' has joined the game.")
    
    def process_player_left(self, request):
        player_name = request.get('player')
        print(f"Player '{player_name}' has left the game.")

    def process_new_creator(self, request):
        new_creator = request.get('player')
        print(f"Player '{new_creator}' is now the game creator.")

    def process_game_started(self, request):
        print(request['message'])
        print("Game has started! Get ready for the first question.")

    def process_question(self, request):
        question = request.get('question')
        print(f"\nQuestion: {question}")
        answer = self.get_valid_answer()
        answer_message = {
            "action": "answer",
            "answer": answer
        }
        Message.send(self.client_socket, answer_message)

    def get_valid_answer(self):
        answer = input("Your answer (true/false): ").strip().lower()
        while answer not in ['true', 'false']:
            print("Invalid answer format. Please reply with 'True' or 'False'.")
            answer = input("Your answer (true/false): ").strip().lower()
        return answer
    
    def question_response(self, request):
        print("Question:", request['question'])
        answer = input("Your answer (true/false): ")
        answer_message = {
            "action": "answer",
            "answer": answer
        }
        Message.send(self.client_socket, answer_message)
    
    def process_answer_feedback(self, request):
        feedback = request.get('message')
        score = request.get('score')
        print(f"\n{feedback}")
        if score is not None:
            print(f"Your current score: {score}\n")
    
    def process_score_update(self, request):
        scores = request.get('scores', {})
        print("\n--- Current Game Scores ---")
        for player, score in scores.items():
            print(f"{player}: {score}")
        print("---------------------------\n")
        
    def process_game_over(self, request):
        message = request.get('message')
        print(f"\n{message}")
        play_again = input("Do you want to play again? (yes/no): ").strip().lower()
        if play_again in ['yes', 'y']:
            self.reset_game()
        else:
            self.notify_disconnect()

    def process_tie_breaker(self, request):
        message = request.get('message')
        print(f"\n{message}")

    def process_error(self, request):
        error_message = request.get('message')
        print(f"\nError: {error_message}")

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
    
    def start(self):
        try:
            while True:
                events = self.sel.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, key.events)
        except KeyboardInterrupt:
            logging.info("\nClient shutting down.")
            self.notify_disconnect()
        finally:
            self.sel.close()
    
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