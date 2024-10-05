import socket
import selectors
import argparse
import logging
import json

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
    
    def send_answer(self, question, answer):
        message = json.dumps({'answer': answer, 'correct_answer': question['correct_answer']})
        self.client_socket.send(message.encode('utf-8'))
        response = self.client_socket.recv(1024).decode('utf-8')
        logging.info(f"Received response: {response}")
    
    def start(self):
        while True:
            data = json.loads(self.client_socket.recv(1024).decode('utf-8'))
            logging.info(f"Question: {data['question']}")
            logging.info(f"Choices: {', '.join(data['choices'])}")
            answer = input('Enter your answer: ')
            self.send_answer(data, answer)
    
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
