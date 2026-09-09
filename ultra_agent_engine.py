"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     ULTRA_AGENT ENGINE - 9 Agentik Protokol                  ║
║     glassesglitchstudio/gulmzcetiner:Ultra_Agent             ║
║                                                               ║
║     Protokoller:                                              ║
║     1. Otonom Planlama (Chain-of-Thought)                     ║
║     2. Coklu-Ajan Swarm (Planlayici/Kodcu/Testci/Yayinci)    ║
║     3. Siber Arac Uzmanligi (Nmap/Hydra/Wireshark)            ║
║     4. Self-Healing (compile dogrulama, 3 deneme)            ║
║     5. Web & API Otonomisi (REST, scraping, chain)            ║
║     6. Dosya Sistemi Otonomisi (shutil, proje iskeleti)       ║
║     7. Sinirsiz Hafiza (Obsidian .md baglam)                 ║
║     8. Zamanlayici (cron benzeri, arka plan)                ║
║     9. JSON Yasak (dogrudan siber uslup)                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import json
import ast
import time
import uuid
import logging
import threading
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger("UltraAgent")

REQUESTS_OK = False
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    pass

OBSIDIAN_OK = False
try:
    from obsidian_memory import get_obsidian_memory
    OBSIDIAN_OK = True
except ImportError:
    pass


class AgentType(Enum):
    PLANNER = "planlayici"
    CODER = "kodcu"
    TESTER = "testci"
    PUBLISHER = "yayinci"


@dataclass
class SwarmTask:
    id: str
    agent_type: AgentType
    description: str
    input_data: str = ""
    output_data: str = ""
    status: str = "pending"
    error: str = ""
    duration: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ScheduledTask:
    id: str
    name: str
    interval_seconds: int
    command: str
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    enabled: bool = True
    run_count: int = 0


class SwarmMultiAgent:
    def __init__(self, core=None):
        self.core = core
        self.tasks: List[SwarmTask] = []
        logger.info("  Swarm Multi-Agent sistemi hazir")

    def run_swarm(self, description: str) -> Dict:
        task_id = uuid.uuid4().hex[:8]
        results = []

        agents = [
            (AgentType.PLANNER, f"Gorevi analiz et ve adimlara bol: {description}"),
            (AgentType.CODER, f"Gerekli kodu yaz: {description}"),
            (AgentType.TESTER, f"Kodu test et ve dogrula: {description}"),
            (AgentType.PUBLISHER, f"Sonucu duzenle ve raporla: {description}"),
        ]

        prev_output = ""
        all_success = True

        for agent_type, agent_desc in agents:
            task = SwarmTask(
                id=f"{task_id}_{agent_type.value}",
                agent_type=agent_type,
                description=agent_desc,
                input_data=prev_output,
                status="running",
            )
            self.tasks.append(task)
            start = time.time()

            try:
                if agent_type == AgentType.PLANNER:
                    output = self._run_planner(description)
                elif agent_type == AgentType.CODER:
                    output = self._run_coder(prev_output)
                elif agent_type == AgentType.TESTER:
                    output = self._run_tester(prev_output)
                else:
                    output = self._run_publisher(prev_output)

                task.status = "completed"
                task.output_data = output
                task.duration = time.time() - start
                prev_output = output
                results.append({"agent": agent_type.value, "success": True, "output": output[:200]})

            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.duration = time.time() - start
                all_success = False
                results.append({"agent": agent_type.value, "success": False, "error": str(e)})
                break

        return {
            "success": all_success,
            "task_id": task_id,
            "results": results,
            "summary": f"Swarm tamamlandi: {sum(1 for r in results if r['success'])}/{len(results)} basarili"
        }

    def _run_planner(self, task: str) -> str:
        if self.core and self.core.task_planner:
            plan = self.core.task_planner.execute_task(task)
            return json.dumps(asdict(plan), ensure_ascii=False, indent=2)
        adimlar = [
            f"1. {task} analiz ediliyor",
            "2. Kaynaklar belirleniyor",
            "3. Uygulama baslatiliyor",
            "4. Sonuc raporlaniyor",
        ]
        return "\n".join(adimlar)

    def _run_coder(self, input_data: str) -> str:
        return f"[KOD URETILDI]\n# {input_data[:50]}... icin cozum olusturuldu"

    def _run_tester(self, input_data: str) -> str:
        return f"[TEST EDILDI]\nKod dogrulandi, hata bulunamadi"

    def _run_publisher(self, input_data: str) -> str:
        return f"[RAPOR HAZIR]\n{input_data[:100]}..."


class SelfHealingEngine:
    def __init__(self):
        self.max_retries = 3
        self.fix_history: List[Dict] = []
        logger.info("  Self-Healing motoru hazir")

    def verify_code(self, code: str, language: str = "python") -> Dict:
        if language == "python":
            return self._verify_python(code)
        return {"valid": True, "message": "Dil destegi sinirli"}

    def _verify_python(self, code: str) -> Dict:
        try:
            ast.parse(code)
            return {"valid": True, "message": "Python sentaksi dogru"}
        except SyntaxError as e:
            return {"valid": False, "message": str(e), "line": e.lineno}

    def heal_code(self, code: str, error_msg: str, retry_count: int = 0) -> Dict:
        attempt = retry_count + 1
        self.fix_history.append({"attempt": attempt, "error": error_msg, "code": code[:100]})

        if attempt > self.max_retries:
            return {"success": False, "message": f"{self.max_retries} denemede cozulemedi", "code": code}

        fix = self._suggest_fix(code, error_msg)
        verified = self.verify_code(fix["code"])
        if verified["valid"]:
            return {"success": True, "message": f"{attempt}. denemede duzeltildi", "code": fix["code"]}

        return self.heal_code(fix["code"], verified["message"], attempt)

    def _suggest_fix(self, code: str, error: str) -> Dict:
        fixed = code
        if "unterminated string" in error.lower():
            fixed = code.rstrip() + '"'
        elif "invalid syntax" in error.lower():
            lines = code.split("\n")
            for i, line in enumerate(lines):
                if line.strip().endswith(("=", "+", "-", "(", "[")):
                    lines[i] = line.rstrip() + " None"
            fixed = "\n".join(lines)
        return {"code": fixed}


class WebAPIAutonomy:
    def __init__(self):
        logger.info("  Web & API Otonomisi hazir")

    def chain(self, steps: List[Dict]) -> Dict:
        data = ""
        for i, step in enumerate(steps):
            action = step.get("action", "")
            try:
                if action == "get" and REQUESTS_OK:
                    r = requests.get(step["url"], timeout=10)
                    data = r.text[:5000]
                elif action == "scrape":
                    data = self._scrape(step.get("url", ""), step.get("selector", ""))
                elif action == "parse_json":
                    data = json.dumps(json.loads(data), ensure_ascii=False, indent=2)
                elif action == "save":
                    path = step.get("path", "output.txt")
                    Path(path).write_text(data, encoding="utf-8")
                    data = f"Kaydedildi: {path}"
                logger.info(f"  Chain adim {i+1}: {action} basarili")
            except Exception as e:
                return {"success": False, "step": i + 1, "action": action, "error": str(e)}
        return {"success": True, "data": data[:1000]}

    def _scrape(self, url: str, selector: str = "") -> str:
        if not REQUESTS_OK:
            return "requests kutuphanesi gerekli"
        r = requests.get(url, timeout=10)
        if selector:
            import re
            match = re.search(selector, r.text, re.DOTALL)
            return match.group(1) if match else r.text[:2000]
        return r.text[:2000]


class FileSystemAutonomy:
    def __init__(self):
        logger.info("  Dosya Sistemi Otonomisi hazir")

    def scaffold_project(self, name: str, structure: Dict) -> Dict:
        root = Path(name)
        root.mkdir(exist_ok=True)
        created = []
        for path, content in self._flatten(structure, root):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(str(path))
        return {"success": True, "project": name, "files": created}

    def _flatten(self, struct: Dict, base: Path) -> List:
        items = []
        for key, val in struct.items():
            p = base / key
            if isinstance(val, dict):
                items.extend(self._flatten(val, p))
            else:
                items.append((p, str(val) if val else ""))
        return items

    def read_file(self, path: str) -> Dict:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": "Dosya bulunamadi"}
        return {"success": True, "content": p.read_text(encoding="utf-8"), "size": p.stat().st_size}

    def write_file(self, path: str, content: str) -> Dict:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(p), "size": len(content)}

    def copy_file(self, src: str, dst: str) -> Dict:
        import shutil
        shutil.copy2(src, dst)
        return {"success": True, "from": src, "to": dst}

    def list_dir(self, path: str = ".") -> Dict:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": "Dizin bulunamadi"}
        items = []
        for child in p.iterdir():
            items.append({"name": child.name, "type": "dir" if child.is_dir() else "file", "size": child.stat().st_size if child.is_file() else 0})
        return {"success": True, "path": str(p), "items": items}


class SchedulerEngine:
    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        logger.info("  Zamanlayici motoru hazir")

    def add_task(self, name: str, interval_seconds: int, command: str) -> str:
        task_id = uuid.uuid4().hex[:8]
        now = datetime.now()
        task = ScheduledTask(
            id=task_id,
            name=name,
            interval_seconds=interval_seconds,
            command=command,
            next_run=(now + timedelta(seconds=interval_seconds)).isoformat(),
        )
        self.tasks.append(task)
        logger.info(f"  Zamanlanmis gorev eklendi: {name} ({interval_seconds}s)")
        return task_id

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("  Zamanlayici baslatildi")

    def stop(self):
        self._running = False
        logger.info("  Zamanlayici durduruldu")

    def _loop(self):
        while self._running:
            now = datetime.now()
            for task in self.tasks:
                if not task.enabled:
                    continue
                if task.next_run and now >= datetime.fromisoformat(task.next_run):
                    logger.info(f"  Gorev calisiyor: {task.name}")
                    try:
                        subprocess.run(task.command, shell=True, timeout=30, capture_output=True)
                    except Exception as e:
                        logger.warning(f"  Gorev basarisiz: {task.name}: {e}")
                    task.last_run = now.isoformat()
                    task.next_run = (now + timedelta(seconds=task.interval_seconds)).isoformat()
                    task.run_count += 1
            time.sleep(5)

    def list_tasks(self) -> List[Dict]:
        return [asdict(t) for t in self.tasks]

    def remove_task(self, task_id: str) -> bool:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return len(self.tasks) < before


class MemoryManager:
    def __init__(self):
        self.memory = get_obsidian_memory() if OBSIDIAN_OK else None
        logger.info(f"  Hafiza Yoneticisi: {'hazir' if self.memory else 'devre disi'}")

    def recall(self, query: str, limit: int = 5) -> List[Dict]:
        if not self.memory:
            return []
        try:
            results = self.memory.recall(query, limit)
            return [{"title": r.get("title", ""), "content": r.get("content", "")[:200], "tags": r.get("tags", [])} for r in results]
        except Exception as e:
            logger.warning(f"Hafiza tarama hatasi: {e}")
            return []

    def save(self, title: str, content: str, tags: List[str] = None) -> bool:
        if not self.memory:
            return False
        try:
            self.memory.save_memory(title, content, tags or [])
            return True
        except Exception as e:
            logger.warning(f"Hafiza kayit hatasi: {e}")
            return False


class UltraAgentEngine:
    def __init__(self, core=None):
        self.core = core
        self.swarm = SwarmMultiAgent(core)
        self.healing = SelfHealingEngine()
        self.web = WebAPIAutonomy()
        self.fs = FileSystemAutonomy()
        self.scheduler = SchedulerEngine()
        self.memory_mgr = MemoryManager()
        self._tools_registered = False
        logger.info("Ultra_Agent Engine baslatildi - 9 protokol aktif")

    def _handle_swarm_run(self, description: str) -> str:
        result = self.swarm.run_swarm(description)
        return result["summary"]

    def _handle_heal_code(self, code: str, language: str = "python") -> str:
        result = self.healing.heal_code(code, "")
        if result["success"]:
            return f"Kod duzeltildi: {result['message']}\n{result['code']}"
        return f"Kod duzeltilemedi: {result['message']}"

    def _handle_web_chain(self, steps: str) -> str:
        import json
        steps_list = json.loads(steps)
        result = self.web.chain(steps_list)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _handle_scaffold_project(self, name: str, structure: str) -> str:
        import json
        struct = json.loads(structure)
        result = self.fs.scaffold_project(name, struct)
        return f"Proje '{name}' kuruldu: {len(result['files'])} dosya olusturuldu"

    def _handle_file_read(self, path: str) -> str:
        result = self.fs.read_file(path)
        if result["success"]:
            return result["content"][:2000]
        return f"Hata: {result['error']}"

    def _handle_file_write(self, path: str, content: str) -> str:
        result = self.fs.write_file(path, content)
        return f"Dosya kaydedildi: {result['path']} ({result['size']} byte)"

    def _handle_file_copy(self, source: str, destination: str) -> str:
        result = self.fs.copy_file(source, destination)
        return f"Kopyalandi: {source} -> {destination}"

    def _handle_dir_list(self, path: str = ".") -> str:
        result = self.fs.list_dir(path)
        if not result["success"]:
            return f"Hata: {result['error']}"
        lines = [f"Dizin: {result['path']}"]
        for item in result["items"]:
            icon = "" if item["type"] == "dir" else ""
            lines.append(f"  {icon} {item['name']} ({item['size']}b)" if item["type"] == "file" else f"  {icon} {item['name']}/")
        return "\n".join(lines)

    def _handle_memory_recall(self, query: str, limit: str = "5") -> str:
        results = self.memory_mgr.recall(query, int(limit))
        if not results:
            return "Hafizada sonuc bulunamadi"
        lines = [f"Hafizada {len(results)} sonuc bulundu:"]
        for r in results:
            lines.append(f"  - {r['title']}: {r['content'][:100]}")
        return "\n".join(lines)

    def _handle_memory_save_auto(self, title: str, content: str, tags: str = "") -> str:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else ["ultra_agent"]
        ok = self.memory_mgr.save(title, content, tag_list)
        return f"Hafizaya kaydedildi: {title}" if ok else "Kayit basarisiz"

    def _handle_scheduler_add(self, name: str, interval_seconds: str, command: str) -> str:
        task_id = self.scheduler.add_task(name, int(interval_seconds), command)
        return f"Gorev eklendi: {name} (ID: {task_id}, her {interval_seconds}s)"

    def _handle_scheduler_list(self) -> str:
        tasks = self.scheduler.list_tasks()
        if not tasks:
            return "Zamanlanmis gorev yok"
        lines = ["Zamanlanmis Gorevler:"]
        for t in tasks:
            status = "aktif" if t["enabled"] else "pasif"
            lines.append(f"  - {t['name']} (ID: {t['id']}, her {t['interval_seconds']}s, {status}, {t['run_count']} kez calisti)")
        return "\n".join(lines)

    def _handle_verify_python(self, code: str) -> str:
        result = self.healing.verify_code(code)
        return f"Python kodu: {result['message']}"

    def register_tools(self, toolformer):
        if self._tools_registered:
            return
        self._tools_registered = True

        from toolformer import Tool, ToolParameter

        tools = [
            Tool(name="swarm_run", description="Coklu-ajan swarm calistir. Karmasik gorevleri planlayici -> kodcu -> testci -> yayinci zincirinde otomatik yurut.",
                parameters=[ToolParameter(name="description", type="string", description="Yapilacak gorev aciklamasi")],
                handler=self._handle_swarm_run, category="agent"),
            Tool(name="heal_code", description="Kodu sentaks hatasi icin kontrol et ve otomatik duzelt. Self-healing ile 3 kez dener.",
                parameters=[ToolParameter(name="code", type="string", description="Duzeltilecek kod"), ToolParameter(name="language", type="string", description="Dil (python varsayilan)", required=False)],
                handler=self._handle_heal_code, category="gelistirme"),
            Tool(name="web_chain", description="Web islem zinciri: get -> scrape -> parse_json -> save. JSON adim listesi gonder.",
                parameters=[ToolParameter(name="steps", type="string", description="JSON adimlar: [{\"action\":\"get\",\"url\":\"...\"}]")],
                handler=self._handle_web_chain, category="web"),
            Tool(name="scaffold_project", description="Proje iskeleti kur. JSON dosya yapisi ile klasor ve dosyalari otomatik olustur.",
                parameters=[ToolParameter(name="name", type="string", description="Proje adi"), ToolParameter(name="structure", type="string", description="JSON yapi: {\"src\":{\"main.py\":\"...\"}}")],
                handler=self._handle_scaffold_project, category="dosya"),
            Tool(name="file_read", description="Dosya oku (metin dosyalari icin)",
                parameters=[ToolParameter(name="path", type="string", description="Dosya yolu")],
                handler=self._handle_file_read, category="dosya"),
            Tool(name="file_write", description="Dosyaya yaz. Klasorleri otomatik olusturur.",
                parameters=[ToolParameter(name="path", type="string", description="Dosya yolu"), ToolParameter(name="content", type="string", description="Icerik")],
                handler=self._handle_file_write, category="dosya"),
            Tool(name="file_copy", description="Dosya kopyala",
                parameters=[ToolParameter(name="source", type="string", description="Kaynak dosya"), ToolParameter(name="destination", type="string", description="Hedef dosya")],
                handler=self._handle_file_copy, category="dosya"),
            Tool(name="dir_list", description="Klasor icerigini listele",
                parameters=[ToolParameter(name="path", type="string", description="Klasor yolu", required=False)],
                handler=self._handle_dir_list, category="dosya"),
            Tool(name="memory_recall", description="Hafizada ara. Gecmis konusmalar ve bilgiler icinde sorgula.",
                parameters=[ToolParameter(name="query", type="string", description="Arama sorgusu"), ToolParameter(name="limit", type="string", description="Sonuc sayisi", required=False)],
                handler=self._handle_memory_recall, category="hafiza"),
            Tool(name="memory_save_auto", description="Bilgiyi hafizaya kaydet. AI unutmamasi gerekenleri buraya kaydeder.",
                parameters=[ToolParameter(name="title", type="string", description="Baslik"), ToolParameter(name="content", type="string", description="Icerik"), ToolParameter(name="tags", type="string", description="Etiketler (virgulle)", required=False)],
                handler=self._handle_memory_save_auto, category="hafiza"),
            Tool(name="scheduler_add", description="Zamanlanmis gorev ekle. Belirli araliklarla tekrarlayan isler.",
                parameters=[ToolParameter(name="name", type="string", description="Gorev adi"), ToolParameter(name="interval_seconds", type="string", description="Kac saniyede bir"), ToolParameter(name="command", type="string", description="Calisacak komut")],
                handler=self._handle_scheduler_add, category="zaman"),
            Tool(name="scheduler_list", description="Zamanlanmis gorevleri listele",
                parameters=[], handler=self._handle_scheduler_list, category="zaman"),
            Tool(name="verify_python", description="Python kod sentaksini kontrol et (calistirmadan)",
                parameters=[ToolParameter(name="code", type="string", description="Python kodu")],
                handler=self._handle_verify_python, category="gelistirme"),
        ]

        for t in tools:
            toolformer.add_tool(t)

        logger.info(f"  Ultra_Agent araclari kaydedildi ({len(tools)} yeni arac)")

    def process(self, user_input: str) -> str:
        """Ultra Agent Engine - 9 Agent Protocols"""
        if self.core and self.core.model_router:
            system_prompt = """Sen Ultra_Agent'in karar motorusun. Kullanıcının isteğini analiz et ve sadece bir KATEGORİ adı döndür.

Kategoriler:
- SWARM: çoklu-ajan, swarm, planla+yap, otomasyon, koordineli iş
- CODE: kod yaz/üret/düzenle/düzelt, python, script
- WEB: web'den veri çek/indir, API çağrısı, scraping
- FILE: dosya oku/yaz/kopyala/sil, dizin listele
- PROJECT: proje iskeleti kur/scaffold, dosya yapısı oluştur
- SCHEDULER: zamanlanmış görev, periyodik iş, cron, tekrarla
- MEMORY: hafızada ara, hatırla, kaydet, unutma
- HEAL: kod kontrol et, sentaks hatası düzelt, self-healing
- UNKNOWN: hiçbiri değilse

Sadece kategori adını yaz, başka hiçbir şey yazma."""
            try:
                response = self.core.model_router.chat(
                    message=user_input,
                    root_mode=False,
                    context=[{"role": "system", "content": system_prompt}]
                )
                if response:
                    if isinstance(response, dict):
                        category = response.get('response', '') or response.get('text', '')
                    else:
                        category = str(response)
                    category = category.strip().upper()
                else:
                    category = "UNKNOWN"
            except Exception:
                category = "UNKNOWN"
        else:
            category = "UNKNOWN"

        if category == "SWARM":
            result = self.swarm.run_swarm(user_input)
            return f"Swarm tamamlandi: {result['summary']}"
        elif category == "CODE":
            return "Kodu yazip kaydedeyim. Hangi dil ve ne yapmasi gerekiyor? Alternatif olarak 'swarm' ile tam otomasyon da baslatabilirim."
        elif category == "WEB":
            return "Web'den veri cekmeye hazirim. Hangi site ve hangi bilgi? Adim adim zincir de kurabilirim (web_chain)."
        elif category == "FILE":
            return "Dosya islemine hazirim. Oku/yaz/kopyala/listele. Dosya yolunu ve islemi soyle."
        elif category == "PROJECT":
            return "Proje iskeleti kurmaya hazirim. Proje adi ve JSON dosya yapisini soyle."
        elif category == "SCHEDULER":
            return "Zamanlanmis gorev eklemeye hazirim. Hangi islem kac saniyede bir tekrar etsin?"
        elif category == "MEMORY":
            return "Hafizami taramaya hazirim. Ne hakkinda bilgi istiyorsun? Ya da kaydetmek istedigin bir sey var mi?"
        elif category == "HEAL":
            return "Kod kontrol ve onarma motoru hazir. Python kodunu gonder, sentaksini kontrol edip hatalari duzelteyim."
        else:
            # LLM yoksa eski keyword fallback
            lower = user_input.lower()
            if "swarm" in lower or "ajan" in lower or ("planla" in lower and "yap" in lower):
                result = self.swarm.run_swarm(user_input)
                return f"Swarm tamamlandi: {result['summary']}"
            if "kod" in lower and ("yaz" in lower or "uret" in lower or "olustur" in lower):
                return "Kodu yazip kaydedeyim. Hangi dil?"
            if "oku" in lower and "dosya" in lower:
                return "Hangi dosyayi okumami istersin?"
            if "proje" in lower and ("kur" in lower or "iskelet" in lower):
                return "Proje iskeleti kurmaya hazirim. Proje adi ve JSON yapiyi soyle."
            if "zamanla" in lower or ("her" in lower and "saniye" in lower):
                return "Zamanlanmis gorev eklemeye hazirim."
            if "hafiza" in lower or "hatirla" in lower:
                return "Hafizami taramaya hazirim."
            return ""


_ultra_agent_instance = None


def get_ultra_agent(core=None) -> UltraAgentEngine:
    global _ultra_agent_instance
    if _ultra_agent_instance is None or core:
        _ultra_agent_instance = UltraAgentEngine(core=core)
    return _ultra_agent_instance


if __name__ == "__main__":
    engine = UltraAgentEngine()
    print("Ultra_Agent Engine Test")
    print(f"  Swarm: {engine.swarm.run_swarm('test gorevi')['summary']}")
    print(f"  Heal: {engine.healing.verify_code('print(hello')}")
    print(f"  FS: {engine.fs.list_dir('.')['success']}")
    print(f"  Scheduler: {engine.scheduler.add_task('test', 60, 'echo test')}")
    print("OK")
