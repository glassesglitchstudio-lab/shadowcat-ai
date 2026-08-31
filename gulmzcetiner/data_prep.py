"""
GulmezCetinerMax - Egitim Verisi Hazirlama
Elytra-ai | Developer: Berkay

Kullanim:
    python data_prep.py

Bu script, GulmezCetinerMax icin egitim verisi hazirlar.
Alpaca formatinda JSON dosyasi olusturur.
"""

import json
import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# 📚 EĞİTİM VERİLERİ - GulmezCetinerMax
# ═══════════════════════════════════════════════════════════════════

# Temel egitim verileri - Buraya kendi verilerini ekle
TRAINING_DATA = [
    # ─── KODLAMA ───
    {
        "instruction": "Python ile bir REST API endpoint yaz.",
        "input": "",
        "output": "from flask import Flask, jsonify, request\n\napp = Flask(__name__)\n\n@app.route('/api/data', methods=['GET'])\ndef get_data():\n    return jsonify({'status': 'success', 'data': []})\n\n@app.route('/api/data', methods=['POST'])\ndef create_data():\n    data = request.json\n    return jsonify({'status': 'created', 'data': data}), 201\n\nif __name__ == '__main__':\n    app.run(debug=True)"
    },
    {
        "instruction": "GDScript ile bir oyuncu kontrol scripti yaz.",
        "input": "",
        "output": "extends CharacterBody2D\n\n@export var speed: float = 300.0\n@export var jump_force: float = -500.0\n\nvar gravity = ProjectSettings.get_setting('physics/2d/default_gravity')\n\nfunc _physics_process(delta):\n    # Gravity\n    if not is_on_floor():\n        velocity.y += gravity * delta\n\n    # Jump\n    if Input.is_action_just_pressed('jump') and is_on_floor():\n        velocity.y = jump_force\n\n    # Horizontal movement\n    var direction = Input.get_axis('move_left', 'move_right')\n    if direction:\n        velocity.x = direction * speed\n    else:\n        velocity.x = move_toward(velocity.x, 0, speed)\n\n    move_and_slide()"
    },
    {
        "instruction": "C++ ile bir linked list implementasyonu yaz.",
        "input": "",
        "output": "#include <iostream>\n\nclass Node {\npublic:\n    int data;\n    Node* next;\n    Node(int val) : data(val), next(nullptr) {}\n};\n\nclass LinkedList {\nprivate:\n    Node* head;\npublic:\n    LinkedList() : head(nullptr) {}\n\n    void insert(int val) {\n        Node* newNode = new Node(val);\n        newNode->next = head;\n        head = newNode;\n    }\n\n    void display() {\n        Node* current = head;\n        while (current) {\n            std::cout << current->data << \" -> \";\n            current = current->next;\n        }\n        std::cout << \"nullptr\" << std::endl;\n    }\n\n    ~LinkedList() {\n        while (head) {\n            Node* temp = head;\n            head = head->next;\n            delete temp;\n        }\n    }\n};"
    },
    {
        "instruction": "HTML/CSS ile modern bir login formu tasarla.",
        "input": "",
        "output": "<!DOCTYPE html>\n<html lang=\"tr\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Login - GulmezCetinerMax</title>\n    <style>\n        * { margin: 0; padding: 0; box-sizing: border-box; }\n        body {\n            display: flex; justify-content: center; align-items: center;\n            min-height: 100vh; background: #0a0a0a; font-family: 'Segoe UI', sans-serif;\n        }\n        .login-container {\n            background: rgba(255,255,255,0.05); backdrop-filter: blur(10px);\n            border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;\n            padding: 40px; width: 380px; text-align: center;\n        }\n        .login-container h2 { color: #ff6600; margin-bottom: 30px; }\n        input {\n            width: 100%; padding: 12px 16px; margin: 8px 0;\n            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);\n            border-radius: 8px; color: white; font-size: 14px;\n        }\n        input:focus { outline: none; border-color: #ff6600; }\n        button {\n            width: 100%; padding: 12px; margin-top: 20px;\n            background: #ff6600; border: none; border-radius: 8px;\n            color: white; font-size: 16px; font-weight: 600; cursor: pointer;\n            transition: all 0.3s ease;\n        }\n        button:hover { background: #ff8533; transform: translateY(-2px); }\n    </style>\n</head>\n<body>\n    <div class=\"login-container\">\n        <h2>GulmezCetinerMax</h2>\n        <input type=\"text\" placeholder=\"Kullanici Adi\">\n        <input type=\"password\" placeholder=\"Sifre\">\n        <button>Giris Yap</button>\n    </div>\n</body>\n</html>"
    },
    {
        "instruction": "JavaScript ile bir debounce fonksiyonu yaz.",
        "input": "",
        "output": "/**\n * Debounce fonksiyonu - Belirli bir sure gecikten sonra calisir\n * @param {Function} func - Cagrilacak fonksiyon\n * @param {number} wait - Bekleme suresi (ms)\n * @returns {Function} Debounced fonksiyon\n */\nfunction debounce(func, wait = 300) {\n    let timeout;\n    return function executedFunction(...args) {\n        const later = () => {\n            clearTimeout(timeout);\n            func(...args);\n        };\n        clearTimeout(timeout);\n        timeout = setTimeout(later, wait);\n    };\n}\n\n// Kullanim:\nconst handleSearch = debounce((query) => {\n    console.log('Arama yapiliyor:', query);\n    // API cagrisi yap\n}, 500);\n\n// Her tus basiniminda cagrilsa bile, 500ms sonra bir kez calisir\ndocument.getElementById('search').addEventListener('input', (e) => {\n    handleSearch(e.target.value);\n});"
    },

    # ─── ANALİZ / MANTIK ───
    {
        "instruction": "Bir dizideki en buyuk ikinci sayiyi bul.",
        "input": "[10, 5, 8, 20, 15, 3]",
        "output": "def second_largest(nums):\n    \"\"\"Bir listedeki en buyuk ikinci sayiyi bulur.\"\"\"\n    if len(nums) < 2:\n        return None\n\n    first = second = float('-inf')\n\n    for num in nums:\n        if num > first:\n            second = first\n            first = num\n        elif first > num > second:\n            second = num\n\n    return second if second != float('-inf') else None\n\n# Test\nnums = [10, 5, 8, 20, 15, 3]\nresult = second_largest(nums)\nprint(f'En buyuk ikinci sayi: {result}')  # 15\n\n# Zaman karmaşikliği: O(n)\n# Alan karmaşikliği: O(1)"
    },
    {
        "instruction": "Fibonacci serisinin ilk n elemanini hesapla.",
        "input": "n = 10",
        "output": "def fibonacci(n):\n    \"\"\"Fibonacci serisinin ilk n elemanini dondurur.\"\"\"\n    if n <= 0:\n        return []\n    elif n == 1:\n        return [0]\n\n    series = [0, 1]\n    for i in range(2, n):\n        series.append(series[i-1] + series[i-2])\n\n    return series\n\n# Test\nn = 10\nresult = fibonacci(n)\nprint(f'Fibonacci({n}): {result}')\n# Sonuc: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]\n\n# Zaman karmaşikliği: O(n)\n# Alan karmaşikliği: O(n)"
    },

    # ─── YAZILIM MİMARİSİ ───
    {
        "instruction": "Singleton design pattern'i Python ile implement et.",
        "input": "",
        "output": "class Singleton:\n    _instance = None\n\n    def __new__(cls, *args, **kwargs):\n        if cls._instance is None:\n            cls._instance = super().__new__(cls)\n        return cls._instance\n\n    def __init__(self):\n        # Sadece ilk olusturmada calisir\n        if not hasattr(self, 'initialized'):\n            self.data = {}\n            self.initialized = True\n\n    def set(self, key, value):\n        self.data[key] = value\n\n    def get(self, key):\n        return self.data.get(key)\n\n# Kullanim\ns1 = Singleton()\ns1.set('name', 'GulmezCetinerMax')\n\ns2 = Singleton()\nprint(s2.get('name'))  # 'GulmezCetinerMax'\nprint(s1 is s2)  # True - ayni instance"
    },
    {
        "instruction": "Observer design pattern'i Python ile implement et.",
        "input": "",
        "output": "from abc import ABC, abstractmethod\nfrom typing import List\n\nclass Observer(ABC):\n    @abstractmethod\n    def update(self, message: str) -> None:\n        pass\n\nclass Subject:\n    def __init__(self):\n        self._observers: List[Observer] = []\n        self._state: str = ''\n\n    def attach(self, observer: Observer) -> None:\n        self._observers.append(observer)\n\n    def detach(self, observer: Observer) -> None:\n        self._observers.remove(observer)\n\n    def notify(self) -> None:\n        for observer in self._observers:\n            observer.update(self._state)\n\n    def set_state(self, state: str) -> None:\n        self._state = state\n        self.notify()\n\n# Somut Observer\nclass Logger(Observer):\n    def update(self, message: str) -> None:\n        print(f'[LOG] {message}')\n\nclass AlertSystem(Observer):\n    def update(self, message: str) -> None:\n        if 'error' in message.lower():\n            print(f'[ALERT] Kritik hata: {message}')\n\n# Kullanim\nsubject = Subject()\nsubject.attach(Logger())\nsubject.attach(AlertSystem())\n\nsubject.set_state('Sistem baslatildi')\nsubject.set_state('Veritabani baglantisi kuruldu')\nsubject.set_state('ERROR: Baglanti kopdu')"
    },

    # ─── GÜVENLİK ───
    {
        "instruction": "Python ile guvenli sifre hashleme yap.",
        "input": "",
        "output": "import hashlib\nimport os\nimport secrets\n\ndef hash_password(password: str) -> str:\n    \"\"\"Guvenli sifre hashleme - bcrypt alternatifi.\"\"\"\n    salt = secrets.token_hex(16)\n    hash_obj = hashlib.pbkdf2_hmac(\n        'sha256',\n        password.encode('utf-8'),\n        salt.encode('utf-8'),\n        100000  # Iterasyon sayisi\n    )\n    return f\"{salt}${hash_obj.hex()}\"\n\ndef verify_password(password: str, stored_hash: str) -> bool:\n    \"\"\"Sifre dogrulama.\"\"\"\n    salt, hash_value = stored_hash.split('$')\n    hash_obj = hashlib.pbkdf2_hmac(\n        'sha256',\n        password.encode('utf-8'),\n        salt.encode('utf-8'),\n        100000\n    )\n    return hash_obj.hex() == hash_value\n\n# Kullanim\npassword = 'GuvenliSifre123!'\nhashed = hash_password(password)\nprint(f'Hash: {hashed}')\n\n# Dogrulama\nprint(f'Dogru sifre: {verify_password(password, hashed)}')  # True\nprint(f'Yanlis sifre: {verify_password(\"yanlis\", hashed)}')  # False"
    },

    # ─── VERİTABANI ───
    {
        "instruction": "SQLite ile basit bir veritabani sinifi yaz.",
        "input": "",
        "output": "import sqlite3\nfrom typing import List, Dict, Optional\nfrom contextlib import contextmanager\n\nclass Database:\n    def __init__(self, db_path: str = 'gulmzcetinermax.db'):\n        self.db_path = db_path\n        self._init_db()\n\n    @contextmanager\n    def get_connection(self):\n        conn = sqlite3.connect(self.db_path)\n        conn.row_factory = sqlite3.Row\n        try:\n            yield conn\n            conn.commit()\n        except Exception:\n            conn.rollback()\n            raise\n        finally:\n            conn.close()\n\n    def _init_db(self):\n        with self.get_connection() as conn:\n            conn.execute('''\n                CREATE TABLE IF NOT EXISTS users (\n                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n                    username TEXT UNIQUE NOT NULL,\n                    email TEXT UNIQUE NOT NULL,\n                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n                )\n            ''')\n\n    def insert_user(self, username: str, email: str) -> int:\n        with self.get_connection() as conn:\n            cursor = conn.execute(\n                'INSERT INTO users (username, email) VALUES (?, ?)',\n                (username, email)\n            )\n            return cursor.lastrowid\n\n    def get_user(self, user_id: int) -> Optional[Dict]:\n        with self.get_connection() as conn:\n            row = conn.execute(\n                'SELECT * FROM users WHERE id = ?', (user_id,)\n            ).fetchone()\n            return dict(row) if row else None\n\n    def get_all_users(self) -> List[Dict]:\n        with self.get_connection() as conn:\n            rows = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()\n            return [dict(row) for row in rows]\n\n    def delete_user(self, user_id: int) -> bool:\n        with self.get_connection() as conn:\n            cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))\n            return cursor.rowcount > 0\n\n# Kullanim\ndb = Database()\ndb.insert_user('berkay', 'berkay@nikosoftware.com')\nusers = db.get_all_users()\nprint(users)"
    },
]


def prepare_training_data(
    output_file: str = "gulmzcetinermax_train.json",
    output_dir: str = None
) -> str:
    """
    Egitim verisini hazirla ve kaydet.
    
    Args:
        output_file: Cikti dosya adi
        output_dir: Cikti dizini (varsayilan: gulmzcetiner/)
        
    Returns:
        str: Kaydedilen dosya yolu
    """
    if output_dir is None:
        output_dir = Path(__file__).parent

    output_path = Path(output_dir) / output_file

    # Alpaca formatinda kaydet
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(TRAINING_DATA, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(TRAINING_DATA)} egitim ornegi hazirlandi!")
    print(f"📁 Dosya: {output_path}")

    # Istatistikler
    categories = {
        "kodlama": 0,
        "analiz": 0,
        "mimarisi": 0,
        "guvenlik": 0,
        "veritabani": 0,
    }

    for item in TRAINING_DATA:
        inst = item["instruction"].lower()
        if any(k in inst for k in ["python", "javascript", "html", "css", "gdscript", "c++", "kod"]):
            categories["kodlama"] += 1
        elif any(k in inst for k in ["bul", "hesapla", "fibonacci"]):
            categories["analiz"] += 1
        elif any(k in inst for k in ["pattern", "singleton", "observer", "mimar"]):
            categories["mimarisi"] += 1
        elif any(k in inst for k in ["sifre", "hash", "guvenlik"]):
            categories["guvenlik"] += 1
        elif any(k in inst for k in ["sqlite", "veritabani", "database"]):
            categories["veritabani"] += 1

    print("\n📊 Kategori Dagilimi:")
    for cat, count in categories.items():
        if count > 0:
            print(f"   {cat}: {count}")

    return str(output_path)


if __name__ == "__main__":
    prepare_training_data()
