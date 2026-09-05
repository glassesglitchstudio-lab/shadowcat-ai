"""
Shadowcat Model Listesi API'si
10 modelin tam listesi, HuggingFace linkleri, parametre sayıları, açıklamalar.
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

MODELS = [
    {
        "id": "atlas-3b",
        "name": "Atlas",
        "params": "3B",
        "type": "Ana Asistan",
        "base": "Qwen2.5-3B-Instruct",
        "description": "Günlük sohbet, soru-cevap, asistanlık. Kademeli çalışır: Lite → Flash → Pro → Expert.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Atlas (ana beyin, marka yüzü)",
        "use_cases": ["Sohbet", "Soru-Cevap", "Yönlendirme"],
    },
    {
        "id": "codes-14b",
        "name": "CodeS",
        "params": "14B",
        "type": "Kod Amiral Gemisi",
        "base": "Qwen2.5-14B-Instruct + 6 XLoRA",
        "description": "Tüm yazılım işleri. 6 XLoRA uzman: kod, design, frontend, backend, debug, cyber.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct",
        "license": "Apache 2.0",
        "turkish": "CodeS (kodlama amiral gemisi)",
        "use_cases": ["Kod yazma", "Refactor", "Debug", "Mimari tasarım"],
        "lora_experts": ["kod", "design", "frontend", "backend", "debug", "cyber"],
    },
    {
        "id": "neos-30b",
        "name": "NeoS",
        "params": "30B",
        "type": "Derin Muhakeme",
        "base": "Qwen2.5-32B-Instruct",
        "description": "Zor problemler: matematik, mantık, bilimsel analiz, strateji. Cevap önce düşünce izleri.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-32B-Instruct",
        "license": "Apache 2.0",
        "turkish": "NeoS (yeni nesil derin muhakeme)",
        "use_cases": ["Matematik", "Mantık", "Bilimsel analiz", "Strateji"],
    },
    {
        "id": "lynx-1.5b",
        "name": "Lynx",
        "params": "1.5B",
        "type": "Hız Avcısı",
        "base": "Qwen2.5-1.5B + Elytra NPU",
        "description": "Saniyenin altı cevap. Tek kelime, otomatik tamamlama. Elytra NPU üstünde koşar.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Lynx (vaşak - en hızlı kedi)",
        "use_cases": ["Anlık yanıt", "Kod tamamlama", "Asistan ipucu"],
    },
    {
        "id": "sphynx-7b",
        "name": "Sphynx",
        "params": "7B",
        "type": "Hafıza Ustası",
        "base": "Qwen2.5-7B + CZP Context Zip",
        "description": "Hatırlama + bilgi arama. CZP (Context Zip Leme) 1000x sıkıştırma. Uzun proje hafızası.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Sphynx (tüysüz kedi, hafıza)",
        "use_cases": ["Uzun proje hafızası", "Bilgi arama", "RAG"],
    },
    {
        "id": "aegis-7b",
        "name": "Aegis",
        "params": "7B",
        "type": "Güvenlik Muhafızı",
        "base": "Qwen2.5-7B + shield rules",
        "description": "Jailbreak tespiti, prompt injection yakalama, kod güvenlik taraması.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Aegis (kalkan, güvenlik)",
        "use_cases": ["Güvenlik taraması", "Prompt filtreleme", "Kod audit"],
    },
    {
        "id": "skys-maker-7b",
        "name": "SkyS-Maker",
        "params": "7B",
        "type": "Görsel Sanatçı",
        "base": "SDXL/Flux + LoRA",
        "description": "Kelimeden resim. Diffusion modeli + kendi LoRA ince ayarı. En sona planlı.",
        "huggingface": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "license": "OpenRAIL++",
        "turkish": "SkyS-Maker (gökyüzü sanatçısı)",
        "use_cases": ["İkon üretimi", "İllüstrasyon", "Concept art"],
    },
    {
        "id": "echo-3b",
        "name": "Echo",
        "params": "3B",
        "type": "Ses Modeli",
        "base": "Whisper + TTS",
        "description": "Konuşma: metni sese, sesi komuta çevirmek. Kediyle konuşmak için!",
        "huggingface": "https://huggingface.co/openai/whisper-large-v3",
        "license": "MIT",
        "turkish": "Echo (yankı, ses)",
        "use_cases": ["Ses tanıma", "Konuşma sentezi", "Sesli asistan"],
    },
    {
        "id": "maxcode-24b",
        "name": "MaxCode",
        "params": "24B",
        "type": "Yetkili Admin",
        "base": "Qwen2.5-24B + Admin LoRA",
        "description": "Senin kişisel baş mühendisin. Şifreyle açılır (TCONE22 → .env). Terminal + dosya düzenleme.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-24B-Instruct",
        "license": "Apache 2.0",
        "turkish": "MaxCode (max kod admin)",
        "use_cases": ["Terminal", "Dosya yönetimi", "Proje yönetimi"],
        "auth": "Password-protected (TCONE22)",
    },
    {
        "id": "max-plus-7b",
        "name": "Max+",
        "params": "7B",
        "type": "Router",
        "base": "Qwen2.5-7B + QLoRA",
        "description": "Kategori kararları: her soruyu okur, doğru modele yönlendirir. Orkestra şefi.",
        "huggingface": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "license": "Apache 2.0",
        "turkish": "Max+ (router, yönlendirici)",
        "use_cases": ["Sorgu sınıflandırma", "Model yönlendirme"],
    },
]


class ModelListHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/v1/models" or path == "/api/models":
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
                        "created": 1725400000,  # 2025-09-04
                        "owned_by": "shadowcat-ai",
                        "name": m["name"],
                        "params": m["params"],
                        "type": m["type"],
                        "base": m["base"],
                        "description": m["description"],
                        "huggingface": m["huggingface"],
                        "license": m["license"],
                        "turkish_name": m["turkish"],
                        "use_cases": m["use_cases"],
                    }
                    for m in MODELS
                ],
            }
            self.wfile.write(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))
        elif path == "/v1/models/list" or path == "/models.html":
            # İnsan-okunabilir liste
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = "<html><head><title>Shadowcat Modelleri</title>"
            html += "<style>body{font-family:sans-serif;max-width:900px;margin:20px auto;padding:20px;background:#0e0e16;color:#e0e0e8;}"
            html += "h1{color:#7c3aed;}h2{color:#06b6d4;}.m{background:#1a1a2e;padding:12px;margin:8px 0;border-radius:6px;}"
            html += "a{color:#06b6d4;}</style></head><body>"
            html += "<h1>🐾 Shadowcat Modelleri (10)</h1>"
            for m in MODELS:
                html += f'<div class="m"><h2>{m["name"]} ({m["params"]}) — {m["type"]}</h2>'
                html += f'<p><b>Açıklama:</b> {m["description"]}</p>'
                html += f'<p><b>Base:</b> {m["base"]}</p>'
                html += f'<p><b>Lisans:</b> {m["license"]}</p>'
                html += f'<p><b>HuggingFace:</b> <a href="{m["huggingface"]}">{m["huggingface"]}</a></p>'
                html += f'<p><b>Kullanım:</b> {", ".join(m["use_cases"])}</p></div>'
            html += "</body></html>"
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    port = 8000
    print(f"🐾 Shadowcat Model API — port {port}")
    print("Endpoints:")
    print("  GET /                → JSON listesi")
    print("  GET /v1/models       → JSON listesi (OpenAI uyumlu)")
    print("  GET /v1/models/list  → HTML görünüm")
    print(f"Modeller: {len(MODELS)}")
    for m in MODELS:
        print(f"  • {m['name']} ({m['params']}) — {m['type']}")
    HTTPServer(("127.0.0.1", port), ModelListHandler).serve_forever()
