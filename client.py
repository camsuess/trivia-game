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
        client_socket.setblocking(False)
        self.sel.register(client_socket, selectors.EVENT_READ, self.read_response)
        return client_socket
    
    def read_response(self, sock, mask):
        message = Message()
        message.read(sock)
        if message.request:
            request = message.request
            if request['action'] == "set_name":
                username = input(request['message'])
                response_message = {
                    "action": "set_name",
                    "name": username
                }
                Message.send(self.client_socket, response_message)
            elif request['action'] == "question":
                print("Question:", request['question'])
                answer = input("Your answer (true/false): ")
                answer_message = {
                    "action": "answer",
                    "answer": answer
                }
                Message.send(self.client_socket, answer_message)

            
    def start(self):
        try:
            while True:
                events = client.sel.select()
                for key, _ in events:
                    callback = key.data
                    callback(key.fileobj, key.events)
        except KeyboardInterrupt:
            logging.info("Client shutting down.")
        finally:
            client.close()
    
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
    client.start()
