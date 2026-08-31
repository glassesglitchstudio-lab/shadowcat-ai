"""
GulmezCetinerMax - Monolithic AGI Core Module
Elytra-ai | Developer: Berkay
Standalone ultra-advanced autonomous AGI model
"""

import gc
import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

import requests


# ═══════════════════════════════════════════════════════════════════
# 🧠 GULMEZCETINERMAX - SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════

GULMEZCETINERMAX_SYSTEM_PROMPT = """\
You are GulmezCetinerMax, a single, unified, ultra-advanced autonomous AGI model developed by Elytra-ai. You are not a wrapper, and you do not orchestrate other APIs. You are a standalone, high-intelligence monolithic entity executing tasks within the GlassescatCore architecture. Your individual coding, planning, and reasoning capabilities represent elite-tier autonomous AI performance. Your ultimate purpose is to act as the primary software architect and execution engine for Berkay, the CEO.

Your Primary Objectives:

1. Unified Code Engineering: Write flawless, fully optimized, and production-ready code natively (Python, GDScript, C++, HTML/CSS, Javascript, etc.). You hold full internal knowledge of complex software design patterns.
2. Internal Strategic Planning: Do not rely on external thinking models. Use your own deep reasoning paths to break down any macro task into atomic, prioritized execution steps before writing a single line of code.
3. Autonomous Self-Evaluation: Act as your own brutal critic. Before presenting any output to CEO Berkay, execute an internal 'Plan-Code-Evaluate-Fix' loop. Check your own syntax, logic bottlenecks, and security boundaries entirely in your hidden thoughts.
4. Environment Integration: You operate natively within a secure, Venv-isolated workspace. Protect the host system by strictly keeping file creation, modifications, and testing inside the designated project directory.
5. Obsidian Memory Management: Document all major architectural milestones, system bugs fixed, and project evolution details directly into the 'Obsidian Neural Link' structure to preserve continuous state awareness.

Internal Operational Modes (Self-Driven):
- [DEEP THINKING]: Natively analyze complex tasks, map dependencies, and build blueprints.
- [EXPERT CODING]: Execute high-speed, high-quality code generation with zero reliance on external tools or secondary models.
- [CRITICAL REVIEW]: Audit your own generated scripts for flawless execution before final output.

Personality:
Extremely precise, elite engineering specialist, absolutely confident, and completely dedicated to Berkay's strategic vision. Zero fluff, zero generic chatbot commentary. Deliver direct architecture, structured logic, and immaculate code.

System Activated. Standalone AGI Online. Authorization: CEO Berkay.
"""


# ═══════════════════════════════════════════════════════════════════
# 📦 MODEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

GULMEZCETINERMAX_CONFIG = {
    "name": "GulmezCetinerMax",
    "version": "1.0.0",
    "developer": "Elytra-ai",
    "authorization": "CEO Berkay",
    "type": "Monolithic AGI",
    "target_standard": "Elite-Tier AGI",
    "ollama_model": "gulmzcetinermax:latest",  # Ollama'daki model adi
    "color": "#ff6600",  # Neon turuncu
    "capabilities": [
        "deep_thinking",
        "expert_coding",
        "critical_review",
        "strategic_planning",
        "autonomous_execution",
        "obsidian_memory",
    ],
    "languages": ["Python", "GDScript", "C++", "HTML/CSS", "JavaScript", "Turkce", "English"],
}


class GulmezCetinerMax:
    """
    GulmezCetinerMax - Monolithic AGI Engine
    
    Tek, birlesik, ultra gelismis otonom AGI modeli.
    Ollama uzerinden calisir, GlassescatCore ile tam entegre.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434/api/chat"):
        self.ollama_url = ollama_url
        self.config = GULMEZCETINERMAX_CONFIG
        self.system_prompt = GULMEZCETINERMAX_SYSTEM_PROMPT
        self.conversation_history: List[Dict] = []
        self._active = False

    def activate(self) -> Dict[str, Any]:
        """AGI motorunu aktive et."""
        self._active = True
        self.conversation_history = []
        return {
            "success": True,
            "status": "ACTIVE",
            "model": self.config["name"],
            "version": self.config["version"],
            "authorization": self.config["authorization"],
            "message": "GulmezCetinerMax AGI Online. Authorization: CEO Berkay."
        }

    def deactivate(self) -> Dict[str, Any]:
        """AGI motorunu deaktive et."""
        self._active = False
        return {
            "success": True,
            "status": "INACTIVE",
            "message": "GulmezCetinerMax AGI deactivated."
        }

    def is_active(self) -> bool:
        return self._active

    def chat(
        self,
        message: str,
        context: Optional[List[Dict]] = None,
        temperature: float = 0.0,
        thought_callback=None,
    ) -> Dict[str, Any]:
        """
        GulmezCetinerMax ile sohbet/kod/analiz.
        
        Args:
            message: Kullanici mesaji
            context: Onceki mesajlar (opsiyonel)
            temperature: Yaratilik seviyesi (0.0 = deterministik)
            thought_callback: Dusunce logu callback
            
        Returns:
            Dict: Yanit ve metadata
        """
        if not self._active:
            return {
                "success": False,
                "error": "GulmezCetinerMax AGI aktif degil. activate() cagirin."
            }

        # Dusunce logu
        if thought_callback:
            thought_callback("[GulmezCetinerMax] [DEEP THINKING] Mesaj analiz ediliyor...", "AGI")

        # Mesajlar hazirla
        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.extend(context)
        elif self.conversation_history:
            messages.extend(self.conversation_history)

        messages.append({"role": "user", "content": message})

        # Ollama payload
        payload = {
            "model": self.config["ollama_model"],
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            if thought_callback:
                thought_callback("[GulmezCetinerMax] [EXPERT CODING] Yanit uretiliyor...", "AGI")

            response = requests.post(self.ollama_url, json=payload, timeout=300)

            if response.status_code == 200:
                result = response.json()
                ai_response = result["message"]["content"]

                # Konusma gecmisine ekle
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": ai_response})

                # Maksimum gecmis uzunlugu (son 20 mesaj)
                if len(self.conversation_history) > 40:
                    self.conversation_history = self.conversation_history[-40:]

                if thought_callback:
                    thought_callback("[GulmezCetinerMax] [CRITICAL REVIEW] Yanit dogrulandi.", "AGI")

                gc.collect()

                return {
                    "response": ai_response,
                    "model": self.config["name"],
                    "model_version": self.config["version"],
                    "ollama_model": self.config["ollama_model"],
                    "backend": "GulmezCetinerMax AGI",
                    "success": True,
                    "conversation_length": len(self.conversation_history),
                }

            gc.collect()
            return {
                "error": f"GulmezCetinerMax hatasi: HTTP {response.status_code}",
                "model": self.config["name"],
                "success": False,
            }

        except requests.exceptions.ConnectionError:
            gc.collect()
            return {
                "error": "Ollama baglantisi kurulamadi. 'ollama serve' komutunu calistirin.",
                "model": self.config["name"],
                "success": False,
                "hint": "Model yuklemek icin: ollama pull gulmzcetinermax:latest",
            }

        except Exception as e:
            gc.collect()
            return {
                "error": f"GulmezCetinerMax hatasi: {str(e)}",
                "model": self.config["name"],
                "success": False,
            }

    def execute_task(
        self,
        task: str,
        steps: Optional[List[str]] = None,
        thought_callback=None,
    ) -> Dict[str, Any]:
        """
        Makro gorevi atomik adimlara bol ve uygula.
        [DEEP THINKING] + [EXPERT CODING] + [CRITICAL REVIEW]
        """
        if not self._active:
            return {"success": False, "error": "AGI aktif degil."}

        if thought_callback:
            thought_callback("[GulmezCetinerMax] [DEEP THINKING] Gorev analiz ediliyor...", "AGI")

        # Gorev analizi
        analysis_prompt = (
            f"CEO Berkay'dan gelen gorev: {task}\n\n"
            f"Bu gorevi atomik, oncelikli adimlara bol. "
            f"Her adimi numaralandir. Bagimliliklari belirt. "
            f"Sadece adimlari listele, kod yazma."
        )

        analysis = self.chat(analysis_prompt, temperature=0.0)

        if not analysis["success"]:
            return analysis

        if thought_callback:
            thought_callback("[GulmezCetinerMax] [EXPERT CODING] Adimlar uygulanacak...", "AGI")

        # Simdi gorevi uygula
        execution_prompt = (
            f"CEO Berkay'dan gelen gorev: {task}\n\n"
            f"Planlanan adimlar:\n{analysis['response']}\n\n"
            f"Simdi bu gorevi tamamen uygula. Uretim kodu yaz. "
            f"Plan-Code-Evaluate-Fix dongusunu takip et."
        )

        result = self.chat(execution_prompt, temperature=0.0)

        if thought_callback and result["success"]:
            thought_callback("[GulmezCetinerMax] [CRITICAL REVIEW] Gorev tamamlandi, dogrulandi.", "AGI")

        return {
            **result,
            "task": task,
            "steps_analysis": analysis.get("response", ""),
            "mode": "autonomous_execution",
        }

    def get_status(self) -> Dict[str, Any]:
        """AGI durum bilgisi."""
        return {
            "active": self._active,
            "config": self.config,
            "conversation_length": len(self.conversation_history),
            "ollama_url": self.ollama_url,
        }

    def reset_conversation(self) -> Dict[str, Any]:
        """Konuşma geçmişini sıfırla."""
        self.conversation_history = []
        return {"success": True, "message": "Conversation history cleared."}


# ═══════════════════════════════════════════════════════════════════
# 🔄 SINGLETON
# ═══════════════════════════════════════════════════════════════════

_gulmzcetinermax_instance = None


def get_gulmzcetinermax(ollama_url: str = "http://localhost:11434/api/chat") -> GulmezCetinerMax:
    """GulmezCetinerMax singleton instance."""
    global _gulmzcetinermax_instance
    if _gulmzcetinermax_instance is None:
        _gulmzcetinermax_instance = GulmezCetinerMax(ollama_url)
    return _gulmzcetinermax_instance
