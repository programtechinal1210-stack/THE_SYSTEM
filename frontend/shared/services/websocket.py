# shared/services/websocket.py
import json
import websocket
import threading
from django.conf import settings

class WebSocketService:
    def __init__(self):
        self.ws = None; self.callbacks = []; self.is_connected = False
    
    def connect(self, url=None):
        ws_url = url or getattr(settings, 'WEBSOCKET_URL', 'ws://127.0.0.1:8000/ws/')
        self.ws = websocket.WebSocketApp(ws_url, on_open=self.on_open, on_message=self.on_message, on_close=self.on_close, on_error=self.on_error)
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
    
    def on_open(self, ws): self.is_connected = True; print("🔌 WebSocket متصل")
    def on_message(self, ws, message):
        data = json.loads(message)
        for callback in self.callbacks: callback(data)
    def on_close(self, ws, close_status_code, close_msg): self.is_connected = False; print("🔌 WebSocket مغلق")
    def on_error(self, ws, error): print(f"❌ WebSocket خطأ: {error}")
    def send(self, data):
        if self.is_connected and self.ws: self.ws.send(json.dumps(data))
    def add_callback(self, callback): self.callbacks.append(callback)
