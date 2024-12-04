import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from unittest.mock import patch, MagicMock
from app.server import GameRoom

class TestGameRoom(unittest.TestCase):

    def test_is_full(self):
        self.gr = GameRoom(123, 3)
        self.gr.players.append("cam")
        self.gr.players.append("dave")
        self.gr.players.append("tim")
        self.assertTrue(self.gr.is_full())

if __name__ == "__main__":
    unittest.main()
