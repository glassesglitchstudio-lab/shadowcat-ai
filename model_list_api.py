# -*- coding: utf-8 -*-
"""
Shadowcat Model Listesi API'si
Sadece egitimi tamamlanmis modeller gosterilir.
TAMAMLANAN: Max+ 3B, Aegis-Cyber 7B
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

MODELS = [
    {
        "id": "maxplus-3b",
        "name": "Max+",
        "params": "3B",
        "type": "Router - Orkestra Sefi",
        "base": "Qwen2.5-3B-Instruct",
        "description": "Sorgu siniflandirma, model yonlendirme, orkestra sefi. Ollamada canli (86-94 tok/s).",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Max+ (router, orkestra sefi) - EGITILDI",
        "use_cases": ["Model yonlendirme", "Sorgu siniflandirma", "Orkestra"],
        "status": "ready"
    },
    {
        "id": "aegis-cyber-7b",
        "name": "Aegis-Cyber",
        "params": "7B",
        "type": "Siber Guvenlik Muhafizi",
        "base": "Qwen2.5-7B + RovX Shield",
        "description": "Siber guvenlik, jailbreak korumasi, kod zirhlama. CYBER22 sifreli yetki.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Aegis-Cyber (siber guvenlik) - EGITILDI",
        "use_cases": ["Guvenlik denetimi", "Jailbreak engelleme", "Kod zirhlama"],
        "status": "ready"
    }
]

# Diger modeller egitim asamasinda - henuz gosterilmiyor
_MODELS_PLANNED = [
    {"id": "atlas-3b", "name": "Atlas", "params": "3B", "type": "Ana Asistan", "status": "planned"},
    {"id": "codes-14b", "name": "CodeS", "params": "14B", "type": "Kod", "status": "planned"},
    {"id": "neos-30b", "name": "NeoS", "params": "30B", "type": "Derin Muhakeme", "status": "planned"},
    {"id": "lynx-1.5b", "name": "Lynx", "params": "1.5B", "type": "Hiz", "status": "planned"},
    {"id": "sphynx-7b", "name": "Sphynx", "params": "7B", "type": "Hafiza", "status": "planned"},
    {"id": "maxplus-7b", "name": "Max+ 7B", "params": "7B", "type": "Router Hedef", "status": "training"},
    {"id": "maxcode-24b", "name": "MaxCode", "params": "24B", "type": "Admin", "status": "planned"},
    {"id": "skys-maker-7b", "name": "SkyS-Maker", "params": "7B", "type": "Gorsel", "status": "planned"},
    {"id": "echo-3b", "name": "Echo", "params": "3B", "type": "Ses", "status": "planned"}
]


class ModelListHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ["/", "/v1/models", "/api/models"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = {
                "object": "list",
                "data": [
                    {
                        "id": m["id"],
                        "object": "model",
                        "created": 1725400000,
                        "owned_by": "shadowcat-ai",
                        "name": m["name"],
                        "params": m["params"],
                        "type": m["type"],
                        "status": m.get("status", "ready"),
                    }
                    for m in MODELS
                ],
            }
            self.wfile.write(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def get_models():
    return MODELS


if __name__ == "__main__":
    port = 8001
    print(f"Shadowcat Model API - port {port}")
    print(f"Toplam model: {len(MODELS)}")
    [print(f"  OK {m['name']} ({m['params']})") for m in MODELS]
    server = HTTPServer(("0.0.0.0", port), ModelListHandler)
    server.serve_forever()
