import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from unittest.mock import patch, MagicMock
from app.server import GameRoom, GameServer, Player

class TestGameRoom(unittest.TestCase):

    def test_is_full(self):
        self.gr = GameRoom(123, 3)
        self.gr.players.append("cam")
        self.gr.players.append("dave")
        self.gr.players.append("tim")
        self.assertTrue(self.gr.is_full())

class TestGameServer(unittest.TestCase):

    @patch('socket.socket')
    def setUp(self, mock_socket):
        self.mock_server_socket = MagicMock()
        mock_socket.return_value = self.mock_server_socket
        self.server = GameServer('127.0.0.1', 12345, 2)

    def tearDown(self):
        self.server.server_socket.close()

    def test_create_server_socket(self):
        self.mock_server_socket.bind.assert_called_once_with(('127.0.0.1', 12345))
        self.mock_server_socket.listen.assert_called_once()

    def test_send_message(self):
        mock_player = Player(MagicMock(), ('127.0.0.1', 12345))
        self.server.send_message(mock_player, {"action": "test", "message": "Hello World"})
        self.assertIn(b'{"action": "test", "message": "Hello World"}', mock_player.send_buffer)

if __name__ == "__main__":
    unittest.main()
