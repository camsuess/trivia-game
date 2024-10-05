import logging
import json
import requests
import socket
import selectors
import types
import argparse

class GameServer:
    def __init__(self, host, port):
        self.sel = selectors.DefaultSelector()
        self.host = host
        self.port = port
        self.clients = set()