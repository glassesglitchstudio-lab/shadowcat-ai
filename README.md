# Shadowcat.AI

Ollama tabanlı otonom AI asistanı. FastAPI backend, WebSocket streaming, RAG, task scheduler ve plugin sistemi.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

## Özellikler

- **AI Sohbet** — WebSocket ile token-token streaming yanıt
- **RAG Sistemi** — PDF/TXT/MD belgeleri yükle, AI'a okut
- **Task Scheduler** — Otonom görevleri zamanla, web'den yönet
- **Plugin Sistemi** — 15 hook, hot-reload, çok dilli
- **Obsidian Hafıza** — Sınırsız .md hafıza sistemi
- **Model Routing** — Görev türüne göre otomatik model seçimi
- **Güvenlik** — AES-256 model şifreleme, brute-force koruması

## Mimari

```
main.py (FastAPI, port 8000)
├── routes/
│   ├── chat.py          → /api/chat, /api/chat/ws (WebSocket)
│   ├── memory.py        → /api/memory/*
│   ├── auth.py          → /api/auth/*
│   ├── admin.py         → /api/admin/*
│   ├── rag.py           → /api/rag/*
│   ├── scheduler.py     → /api/scheduler/*
│   ├── vision.py        → /api/vision/*
│   ├── tts.py           → /api/tts/*
│   ├── code_agent.py    → /api/agent/*
│   ├── qwen.py          → /api/qwen/*
│   ├── sandbox.py       → /api/sandbox/*
│   ├── venv.py          → /api/venv/*
│   ├── code.py          → /api/code/*
│   ├── files.py         → /api/files/*
│   ├── search.py        → /api/search/*
│   ├── models.py        → /api/models/*
│   ├── plugins.py       → /api/plugins/*
│   ├── skills.py        → /api/skills/*
│   ├── theme.py         → /api/theme/*
│   ├── tools.py         → /api/tools/*
│   └── system.py        → /api/system/*
├── middleware/
│   └── auth.py          → Oturum yönetimi
├── glassescat_core.py   → Ana AI motoru
├── model_router.py      → Akıllı model seçimi
├── toolformer.py        → 24 araçlı fonksiyon çağırma
├── obsidian_memory.py   → Sınırsız .md hafıza
├── rag_system.py        → FAISS + sentence-transformers
├── task_scheduler.py    → Zamanlanmış görevler
├── plugin_system.py     → 15 hook plugin motoru
└── web/templates/       → Frontend (HTML/CSS/JS)
```

## Kurulum

### 1. Ollama Kurulumu

```bash
# Windows
https://ollama.com/download adresinden indir

# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Model İndirme

```bash
ollama pull glassesglitchstudio/gulmzcetiner:V3A
```

### 3. Bağımlılıklar

```bash
pip install -r requirements.txt
```

### 4. Çalıştırma

```bash
python main.py
```

Sunucu `http://localhost:8000` adresinde başlar.

## API Endpoint'leri

| Kategori | Endpoint Sayısı | Örnekler |
|----------|----------------|----------|
| Chat (WebSocket) | 3 | `/api/chat`, `/api/chat/ws` |
| Auth | 6 | `/api/auth/login`, `/api/auth/register` |
| Admin | 12 | `/api/admin/keys`, `/api/admin/stats` |
| Memory | 4 | `/api/memory/search`, `/api/memory/stats` |
| RAG | 7 | `/api/rag/upload`, `/api/rag/search` |
| Scheduler | 10 | `/api/scheduler/tasks`, `/api/scheduler/history` |
| Vision | 6 | `/api/vision/analyze`, `/api/vision/ocr` |
| Code Agent | 9 | `/api/agent/analyze`, `/api/agent/generate` |
| Dosya İşlemleri | 9 | `/api/files/read`, `/api/files/write` |
| Arama | 4 | `/api/search`, `/api/search/news` |
| Diğer | 30+ | models, plugins, skills, theme, tools, tts, sandbox, venv, code |

**Toplam: 124+ endpoint**

## Modeller

YENİ MODELERİMİZ GELESEYE KADAR BİRAZ BEKELYİN O EKSİ MODELER TEST İÇİNDİ ARITK CİDDEN MODEL YAPAMYA BAŞLIYORUZ 

## Dizin Yapısı

```
shadowcat/
├── main.py              → FastAPI giriş noktası
├── routes/              → API endpoint'leri (22 dosya)
├── middleware/           → Auth middleware
├── web/templates/       → Frontend HTML
├── web/static/          → CSS, JS, görseller
├── glassescat_core.py   → Ana AI motoru (869 satır)
├── model_router.py      → Model yönlendirici (725 satır)
├── toolformer.py        → Araç sistemi (2088 satır)
├── obsidian_memory.py   → Hafıza sistemi (879 satır)
├── rag_system.py        → RAG motoru (2243 satır)
├── task_scheduler.py    → Görev zamanlayıcı (590 satır)
├── plugin_system.py     → Plugin motoru (1700+ satır)
├── model_security/      → AES-256 model şifreleme
├── gulmzcetiner/        → Model fine-tune dosyaları
└── plugins/             → Plugin dosyaları
```

## Lisans

Apache License 2.0
