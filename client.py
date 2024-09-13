import socket

HOST = '129.82.45.130'
PORT = 7777

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    data = s.recv(1024)
    print('Received:', data.decode())
    while True:
        response = input("Type a message (or 'exit' to quit): ")

        s.sendall(response.encode())

        if response.lower() == 'exit':
            print("Exiting...")
            break

        data = s.recv(1024)
        print('Received from server:', data.decode())