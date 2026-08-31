# Shadowcat AI - Obsidian Sınırsız Hafıza + Otonom Ajan Sistemi

## ZORUNLU: Push & Yayınla Workflow (Unutma!)
Berkay "push la", "yayınla", "github'a at" dediğinde HER ZAMAN:
1. `git add main.py gulmzcetiner/Modelfile docs/ web/ main.py .github/workflows/pages.yml && git commit -m "V5_NEXUS_CORE: ..." && git push origin main`
2. `cd gulmzcetiner && ollama create glassesglitchstudio/gulmzcetiner:V5_NEXUS_CORE -f Modelfile && ollama push glassesglitchstudio/gulmzcetiner:V5_NEXUS_CORE`
3. Link göster: GitHub (glasses-cat-ai) + Ollama (V5_NEXUS_CORE) + GitHub Pages (https://glassesglitchstudio-lab.github.io/glasses-cat-ai)

## ZORUNLU: Oturum Başlangıcı
Her yeni oturumda BU KOMUTU ÇALIŞTIRARAK başla:
```bash
cd C:\Users\ErCuM\CascadeProjects\shadowcat && python -c "from shadowcat_core import get_core; c = get_core(); print(f'Shadowcat Core: {c.get_status()[\"stats\"][\"tools_available\"]} tools, {c.memory.get_memory_count() if c.memory else 0} memory files')"
```

## Yeni Mimari (v3.0)

```
Shadowcat Core (shadowcat_core.py)
  ├── AgentLoop (shadowcat_agent_loop.py)    → ReAct: Düşün + Karar Ver + Uygula
  ├── TaskPlanner (shadowcat_task_planner.py) → Çok adımlı görev planlama
  ├── StateManager (shadowcat_state_manager.py) → Kalıcı durum yönetimi
  ├── WebAgent (shadowcat_web_agent.py)       → Otonom web tarayıcı
  ├── FeedbackLoop (shadowcat_feedback.py)    → Öğrenme ve hata analizi
  ├── Toolformer (toolformer.py)         → 24 araçlı fonksiyon çağırma
  ├── ObsidianMemory (obsidian_memory.py) → Sınırsız .md hafıza
  └── ModelRouter (model_router.py)      → Akıllı model seçimi
```

## Kullanım

### CLI ile başlatma
```bash
cd C:\Users\ErCuM\CascadeProjects\shadowcat && python shadowcat_agent.py
```

### Web sunucusu ile başlatma
```bash
cd C:\Users\ErCuM\CascadeProjects\shadowcat && python main.py
```

### Python'dan kullanma
```python
from shadowcat_core import get_core
core = get_core()

# Tek mesaj
result = core.process_message("Merhaba!")
print(result["response"])

# Çok adımlı görev
result = core.execute_task("Chrome'u aç, YouTube'a gir, Mavislime ara")
print(result["summary"])

# Hafızada ara
if core.memory:
    results = core.memory.recall("python", 5)
```

## Önemli Komutlar (CLI'da)
| Komut | Açıklama |
|-------|----------|
| `yardim` | Yardım menüsü |
| `durum` | Sistem durumu |
| `istatistik` | Performans istatistikleri |
| `planla <görev>` | Çok adımlı görev |
| `ara <sorgu>` | Web'de ara |
| `hafizada ara <s>` | Hafızada ara |
| `ogren` | AI öğrenme istatistikleri |

## Hafızaya Kaydetme
```python
from obsidian_memory import get_obsidian_memory
m = get_obsidian_memory()
m.save_memory(title, content, tags=[])
m.save_conversation(session_id, messages)
m.save_knowledge(title, content, category="general")
```

## Hızlı Test
```bash
cd C:\Users\ErCuM\CascadeProjects\shadowcat && python -c "
from shadowcat_core import get_core
from shadowcat_agent_loop import get_agent_loop
c = get_core()
loop = get_agent_loop(core=c)
r = loop.run(user_input='test')
print('OK' if r['success'] else 'FAIL')
"
```

## Session Notları (2026-07-26)

### Son Çalışma — Glitch Code Provider Bug Fix
- **Bug**: Kullanılmayan provider'lar (cloudflare-ai-gateway vb.) init'te throw atıyordu
- **Fix**: `provider.ts` — throw yerine `{ autoload: false }`, custom loader'lar sadece configured provider'lar için çağrılır
- **Commit**: `d9a31ec` → pushed, Actions ✅
- **Son version**: `glitchcode-cli` v0.4.5

### Orca IDE'ye Geçildi
Bundan sonra VS Code yerine **Orca IDE** (stablyai/orca) kullanılacak. Orca:
- OpenCode/Glitch Code dahil 30+ agent'ı paralel çalıştırır
- Her agent izole git worktree'de çalışır
- Mobil uygulaması var (iOS + Android)
- Windows desteği var (.exe)
- Adres: onorca.dev

### Session Notları (2026-07-30)

#### Claude-Purple UI Tamamlandı
- **docs/index.html**: Bug fix (extra closing tags, cursor none) + Claude-purple landing page (light theme, purple accent #7c3aed, cat logo)
- **web/templates/chat.html**: Full Claude-style chat UI — left sidebar with chat history + new chat, model selector dropdown, welcome screen with suggestion chips, avatar-based messages (cat logo for AI), purple send button, demo mode toggle
- **docs/chat.html**: Synced same design for GitHub Pages standalone
- **.github/workflows/pages.yml**: Created for GitHub Actions deployment
- **Commit**: `eaf328b` → pushed, Pages ✅
- Tüm temalar denendi: warm dark → brass/rust → neon purple → Gemini light → Claude-purple (kabul edildi)

#### Claude Feature Set Implementation (2026-07-30)
**Core v3.1.0** — Style selector, Extended thinking, Project Manager, Message branching, File Upload, Artifacts, Slash commands, Share link, Semantic search
- **shadowcat_core.py**: Added STYLES dict, `set_style()`, `set_personal_preferences()`, `set_extended_thinking()`, `build_custom_system_prompt()`, project CRUD (`create_project`, `list_projects`, `set_active_project`, `add_file_to_project`), message branching (`edit_message`, `switch_branch`, `get_branches`)
- **shadowcat_agent_loop.py**: `run()` accepts `custom_prompt` param, `_build_system_prompt()` appends custom prompt
- **main.py**: API endpoints for styles (`POST/GET /api/settings/style`), preferences (`POST/GET /api/settings/preferences`), extended thinking (`POST /api/settings/extended-thinking`), projects CRUD (`/api/projects`), message branching (`/api/conversations/*/edit`, branches), file upload (`POST /api/upload` with PDF/image/CSV/code parsing), share link (`POST /api/share`, `GET /share/{id}`)
- **web/templates/chat.html**: Complete Claude-style UI with artifacts panel, file upload modal, drag & drop, style selector overlay with personal preferences, extended thinking toggle, web search toggle, slash commands menu, message editing/branching, sidebar search, project tab
- **docs/chat.html**: Synced standalone version for GitHub Pages
- **Commit**: `next`

### Projeler
| Proje | Durum |
|-------|-------|
| glitch-code | ✅ Aktif, v0.4.5, provider fix |
| shadowcat-r1 | ⏸ 761K dataset hazır, Colab Pro+ bekliyor |
| shadowcat (Shadowcat) | ⏸ V7_HYBRID_TITAN |
| deenemee | ✅ Portfolyo hazır |
| jarvis my pc | ⏸ Snapchat entegrasyonu tamam |
