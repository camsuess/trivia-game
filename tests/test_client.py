import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from unittest.mock import patch, MagicMock
from app.client import GameClient


class TestGameClient(unittest.TestCase):

    @patch('socket.socket')
    def setUp(self, mock_socket):
        self.mock_socket_inst = MagicMock()
        mock_socket.return_value = self.mock_socket_inst
        self.client = GameClient('127.0.0.1', 12345)

    def tearDown(self):
        self.client.client_socket.close()

    def test_create_client_socket(self):
        self.mock_socket_inst.connect.assert_called_once_with(('127.0.0.1', 12345))
        self.assertTrue(self.client.running)

    @patch('threading.Lock')
    @patch('json.dumps', return_value='{"action": "test"}')
    def test_send_message(self, mock_json_dumps, mock_Lock):
        self.client.send_message({"action": "test"})
        self.assertIn(b'{"action": "test"}', self.client.send_buffer)

if __name__ == "__main__":
    unittest.main()
