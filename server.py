import requests
import json
import socket

url = "https://the-trivia-api.com/v2/questions"

response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    # print(json.dumps(data, indent=4))
else:
    print("error getting data")

HOST = '129.82.45.130'
PORT = 7777

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST,PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        question = data[0]['question']['text']
        conn.sendall(question.encode())
        print(f"Question sent: {question}")
        while True:
            
            data = conn.recv(1024).decode()

            if not data:
                
                print("Client disconnected")
                break

            print(f"Received from client: {data}")

            if data.lower() == 'exit':
                print("Client requested to exit.")
                break

            conn.sendall(f"Server received: {data}".encode())

        print("Closing connection...")
