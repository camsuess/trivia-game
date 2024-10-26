import socket
import selectors
import argparse
import logging
from message import Message

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

class GameClient:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.client_socket = self.create_client_socket()
    
    def create_client_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.host, self.port))
        return client_socket
    
    def send_answer(self, answer):
        message = {"type": "answer", "content": {"answer": answer}}
        Message.send(self.client_socket, message)
        response = Message.receive(self.client_socket)
        if response:
            logging.info(f"Received response: {response.get('content', {}).get('message', '')}")

    
    def start(self):
        while True:
            try:
                data = Message.receive(self.client_socket)
                if data is None:
                    logging.error("No data received from the server")
                    continue

                logging.info(f"Received data: {data}")

                if isinstance(data, dict) and 'type' in data:
                    if data['type'] == 'message' and data['content'].get('message').strip() == 'Please enter your name:':
                        name = input("Please enter your name: ")
                        Message.send(self.client_socket, {"type": "name", "content": {"name": name}})
                    
                    elif data['type'] == 'question':
                        question = data['content']['question']
                        choices = data['content']['choices']
                        logging.info(f"Question: {question}")
                        logging.info(f"Choices: {', '.join(choices)}")
                        answer = input('Enter your answer: ')
                        self.send_answer(answer)

                    elif data['type'] == 'score_update':
                        logging.info(data['content'].get('message'))
                else:
                    logging.error("Received an improperly formatted message or unknown message type.")
        
            except (ConnectionResetError, socket.error) as e:
                logging.error(f"Connection error: {e}")
                break


    def close(self):
        self.client_socket.close()

def parse_args():
    parser = argparse.ArgumentParser(description='Trivia Game Client', add_help=False)
    
    parser.add_argument('-i', '--ip', type=str, default='127.0.0.1', help='Server IP')
    parser.add_argument('-p', '--port', type=int, required=True, help='Server Port')
    parser.add_argument('-h', '--help', action='help', help='Show help message and exit')
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    client = GameClient(host=args.ip, port=args.port)
    
    try:
        client.start()
    finally:
        client.close()
