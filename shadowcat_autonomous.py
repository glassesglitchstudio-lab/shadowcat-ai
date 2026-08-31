"""
Shadowcat Autonomous System - WebSocket İle Sürekli Bağlantı
Real-time iletişim: Web <-> Godot <-> Shadowcat AI

Çalışma Mantığı:
1. WebSocket sunucu başlar
2. Godot/Web bağlanır
3. Sürekli mesaj alışverişi - otomatik niyet algılama
4. AI yanıt üretir ve kod çalıştırır
"""

import asyncio
import json
import threading
import time
import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from typing import Dict, Optional

# Command Parser import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from command_parser import CommandParser, IntentMode

# Flask + SocketIO
app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.config['SECRET_KEY'] = 'Shadowcat_secret_2024'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ==================== COMMAND PARSER ====================
parser = CommandParser()

# ==================== BAĞLI CLIENTLAR ====================
class ConnectedClients:
    """Bağlı clientları takip et"""
    
    def __init__(self):
        self.clients = {}  # sid -> {type, mode, last_seen}
    
    def add(self, sid: str, client_type: str):
        self.clients[sid] = {
            "type": client_type,
            "mode": "UNKNOWN",
            "last_seen": datetime.now().isoformat(),
            "connected_at": datetime.now().isoformat()
        }
    
    def remove(self, sid: str):
        if sid in self.clients:
            del self.clients[sid]
    
    def update_mode(self, sid: str, mode: str):
        if sid in self.clients:
            self.clients[sid]["mode"] = mode
    
    def get_all(self):
        return self.clients
    
    def broadcast_to_type(self, client_type: str, message: Dict):
        for sid, info in self.clients.items():
            if info["type"] == client_type:
                socketio.emit('message', message, room=sid)

connected_clients = ConnectedClients()

# ==================== USER INTENT OTOMATİK İŞLEME ====================
class IntentProcessor:
    """
    Otomatik niyet işleyici
    Her mesaj geldiğinde otomatik analiz eder
    """
    
    def __init__(self):
        self.last_intent = None
        self.conversation_context = []
        self.auto_respond = True
    
    def process(self, message: str, client_info: Dict = None) -> Dict:
        """Mesajı otomatik işle"""
        # Komut ayrıştır
        result = parser.parse(message)
        
        self.last_intent = result
        self.conversation_context.append({
            "message": message,
            "mode": result["mode"],
            "timestamp": datetime.now().isoformat()
        })
        
        # Otomatik yanıt hazırla
        response = self._create_auto_response(result)
        
        return {
            "intent": result,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_auto_response(self, intent_result: Dict) -> str:
        """Otomatik yanıt oluştur"""
        mode = intent_result["mode"]
        confidence = intent_result["confidence"]
        
        if mode == "[G]":
            return f"Oyun modu algılandı (%{confidence*100:.0f})\nKod üretiliyor..."
        elif mode == "[A]":
            return f"Ajan modu algılandı (%{confidence*100:.0f})\nOtomasyon hazırlanıyor..."
        elif mode == "[S]":
            return f"Sistem modu algılandı (%{confidence*100:.0f})\nSistem kontrol ediliyor..."
        else:
            return "Shadowcat: Mesajınızı işliyorum... "
    
    def get_code(self, intent_result: Dict) -> str:
        """Üretilen kodu al"""
        return intent_result.get("generated_code", "")

intent_processor = IntentProcessor()

# ==================== GODOT ENTEGRASYONU ====================
class GodotBridge:
    """Godot ile iletişim köprüsü"""
    
    def __init__(self):
        self.connected = False
        self.godot_sid = None
    
    def register_godot(self, sid: str):
        self.godot_sid = sid
        self.connected = True
        print(f"Godot bağlandı: {sid}")
    
    def unregister_godot(self):
        self.connected = False
        self.godot_sid = None
        print("Godot bağlantısı koptu")
    
    def send_to_godot(self, event: str, data: Dict):
        """Godot'a mesaj gönder"""
        if self.godot_sid:
            socketio.emit(event, data, room=self.godot_sid)
    
    def execute_game_code(self, code: str):
        """Godot'a kod gönder çalıştır"""
        self.send_to_godot("execute_code", {
            "code": code,
            "timestamp": datetime.now().isoformat()
        })

godot_bridge = GodotBridge()

# ==================== WEBSOCKET ROUTES ====================

@socketio.on('connect')
def handle_connect():
    """Client bağlandığında"""
    print(f"Client bağlandı: {request.sid}")
    emit('connected', {
        'status': 'ok',
        'message': 'Shadowcat\'e hoş geldin!',
        'time': datetime.now().isoformat()
    })

@socketio.on('register')
def handle_register(data):
    """Client tipi kaydet (web/godot)"""
    client_type = data.get('type', 'web')
    connected_clients.add(request.sid, client_type)
    
    if client_type == 'godot':
        godot_bridge.register_godot(request.sid)
        emit('godot_registered', {'status': 'ok'})
    
    print(f"Kayıt: {client_type} - {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Client ayrıldığında"""
    client_info = connected_clients.clients.get(request.sid, {})
    client_type = client_info.get('type', 'unknown')
    
    if client_type == 'godot':
        godot_bridge.unregister_godot()
    
    connected_clients.remove(request.sid)
    print(f"Client ayrıldı: {request.sid}")

@socketio.on('message')
def handle_message(data):
    """
    Ana mesaj işleyici - OTOMATİK NİYET ALGILAMA
    Her gelen mesaj otomatik analiz edilir
    """
    message = data.get('message', '')
    client_info = connected_clients.clients.get(request.sid, {})
    
    if not message:
        return
    
    # OTOMATİK NİYET İŞLEME
    result = intent_processor.process(message, client_info)
    
    # Mode güncelle
    connected_clients.update_mode(request.sid, result["intent"]["mode"])
    
    # Yanıt gönder
    emit('intent_response', {
        'original_message': message,
        'mode': result["intent"]["mode"],
        'confidence': result["intent"]["confidence"],
        'scores': result["intent"]["scores"],
        'response': result["response"],
        'code': result["intent"]["generated_code"],
        'timestamp': result["timestamp"]
    })
    
    # Eğer Godot bağlı ve oyun modu ise kodu gönder
    if result["intent"]["mode"] == "[G]" and godot_bridge.connected:
        code = intent_processor.get_code(result["intent"])
        godot_bridge.execute_game_code(code)

@socketio.on('godot_command')
def handle_godot_command(data):
    """Godot'a özel komut gönder"""
    command = data.get('command', '')
    params = data.get('params', {})
    
    # Komutu işle
    result = intent_processor.process(f"godot komutu: {command}")
    
    emit('godot_response', {
        'command': command,
        'result': result,
        'godot_connected': godot_bridge.connected
    })

@socketio.on('request_status')
def handle_status_request(data):
    """Durum talebi"""
    emit('status', {
        'connected_clients': len(connected_clients.clients),
        'godot_connected': godot_bridge.connected,
        'current_mode': parser.current_mode.value,
        'parser_mode': parser.get_mode_description(parser.current_mode),
        'last_intent': intent_processor.last_intent["mode"] if intent_processor.last_intent else "YOK"
    })

# ==================== HTTP ROUTES ====================

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/api/intent', methods=['POST'])
def http_intent():
    """HTTP ile niyet gönder"""
    data = request.get_json()
    message = data.get('message', '')
    
    result = intent_processor.process(message)
    
    return jsonify({
        "success": True,
        "mode": result["intent"]["mode"],
        "confidence": result["intent"]["confidence"],
        "code": result["intent"]["generated_code"],
        "response": result["response"]
    })

@app.route('/api/status')
def http_status():
    """HTTP durum"""
    return jsonify({
        "connected": len(connected_clients.clients),
        "godot": godot_bridge.connected,
        "mode": parser.current_mode.value
    })

# ==================== TEST SAYFASI ====================
@app.route('/test')
def test_page():
    """Test sayfası - otomatik mesaj gönder"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shadowcat Test</title>
        <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
        <style>
            body { font-family: Arial; padding: 20px; background: #1a1a2e; color: #fff; }
            .box { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .mode-g { color: #00ff88; }
            .mode-a { color: #00d4ff; }
            .mode-s { color: #ff4444; }
            input, button { padding: 10px; margin: 5px; }
            pre { background: #0a0a0f; padding: 10px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>Shadowcat Autonomous Test</h1>
        <div class="box">
            <h3>Bağlantı</h3>
            <button onclick="connect()">Bağlan</button>
            <span id="status">Bağlı değil</span>
        </div>
        <div class="box">
            <h3>Otomatik Test Mesajları</h3>
            <button onclick="sendTest('Şunu yapmak istiyorum: bir oyun')">Oyun Modu</button>
            <button onclick="sendTest('Bot yapmak istiyorum')">Ajan Modu</button>
            <button onclick="sendTest('Sistemi durdur')">Sistem Modu</button>
            <button onclick="sendTest('Platformer oyun yap')">Platformer</button>
        </div>
        <div class="box">
            <h3>Mesaj</h3>
            <input type="text" id="msg" placeholder="Mesajınız..." style="width: 300px;">
            <button onclick="sendCustom()">Gönder</button>
        </div>
        <div class="box">
            <h3>Sonuç</h3>
            <pre id="output"></pre>
        </div>
        <script>
            var socket;
            function connect() {
                socket = io();
                socket.on('connect', () => {
                    document.getElementById('status').innerText = 'BAĞLI';
                    socket.emit('register', {type: 'web'});
                });
                socket.on('intent_response', (data) => {
                    let cls = data.mode === '[G]' ? 'mode-g' : data.mode === '[A]' ? 'mode-a' : 'mode-s';
                    document.getElementById('output').innerHTML = 
                        '<span class="' + cls + '">Mod: ' + data.mode + '</span>\\n' +
                        'Güven: %' + (data.confidence * 100).toFixed(1) + '\\n' +
                        'Yanıt: ' + data.response + '\\n\\nKod:\\n' + data.code;
                });
            }
            function sendTest(msg) {
                socket.emit('message', {message: msg});
            }
            function sendCustom() {
                socket.emit('message', {message: document.getElementById('msg').value});
            }
        </script>
    </body>
    </html>
    """

# ==================== ANA ÇALIŞTIRMA ====================
if __name__ == "__main__":
    print("=" * 60)
    print("  SHADOWCAT AUTONOMOUS SYSTEM")
    print("  WebSocket ile Sürekli Bağlantı")
    print("=" * 60)
    print()
    print("Servisler:")
    print("  - Web Arayüz:   http://localhost:5000")
    print("  - WebSocket:    ws://localhost:5000")
    print("  - Test Sayfası: http://localhost:5000/test")
    print()
    print("Kullanım:")
    print("  1. http://localhost:5000/test aç")
    print("  2. Bağlan butonuna tıkla")
    print("  3. Otomatik test mesajları gönder")
    print()
    print("Godot için:")
    print("  - Godot'ta WebSocket client kullan")
    print("  - localhost:5000 bağlan")
    print("  - register event ile 'godot' tipi gönder")
    print("  - message event ile mesaj gönder")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)