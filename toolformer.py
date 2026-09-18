"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║       TOOLFORMER - Fonksiyon Çağırma Sistemi                    ║
║       Shadowcat AI / Shadowcat için Yapay Zeka Araç Kullanımı       ║
║                                                                  ║
║    Bu sistem, AI modelinin doğal dil anlayışı ile               ║
║    sistem araçlarını (tool) kullanmasını sağlar.                ║
║                                                                  ║
║    Mimarisi:                                                      ║
║    - Tool (Araç) Tanımlama ve Kayıt                              ║
║    - Fonksiyon Çağırma Prompt Şablonu                            ║
║    - AI Yanıtından Araç Çağrısı Çıkartma                         ║
║    - Araç Çalıştırma Motoru                                      ║
║    - Zincirleme Araç Çağrıları                                   ║
║    - Güvenlik ve Onay Sistemi                                    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import math
import time
import ast
import builtins
import datetime
import threading
import subprocess
import traceback
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from pathlib import Path
from abc import ABC, abstractmethod

# =============================================================================
# MODÜL DENETİMİ - İsteğe bağlı bağımlılıklar
# =============================================================================

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import pyautogui
    PYAUTOGUI_OK = True
except ImportError:
    PYAUTOGUI_OK = False

try:
    from plyer import notification
    PLYER_OK = True
except ImportError:
    PLYER_OK = False

# =============================================================================
# VERİ SINIFLARI
# =============================================================================

@dataclass
class ToolParameter:
    """
    Bir aracın parametre tanımı.
    
    Örnek:
        ToolParameter(
            name="query",
            type="string",
            description="Arama sorgusu",
            required=True
        )
    """
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON şemasına dönüştür"""
        schema = {
            "type": self.type,
            "description": self.description
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class Tool:
    """
    Bir aracın tam tanımı.
    
    Örnek:
        Tool(
            name="web_search",
            description="Web'de arama yapar",
            parameters=[ToolParameter(name="query", type="string", description="Arama sorgusu")],
            handler=web_search_handler,
            category="bilgi",
            dangerous=False
        )
    """
    name: str
    description: str
    parameters: List[ToolParameter]
    handler: Callable
    category: str = "genel"
    dangerous: bool = False
    requires_confirmation: bool = False
    examples: List[str] = field(default_factory=list)

    def to_openai_schema(self) -> Dict[str, Any]:
        """OpenAI fonksiyon çağırma formatında şema döndür"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_dict()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Sözlük formatına dönüştür"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [asdict(p) for p in self.parameters],
            "category": self.category,
            "dangerous": self.dangerous,
            "requires_confirmation": self.requires_confirmation,
            "examples": self.examples
        }


@dataclass
class ToolCall:
    """
    AI tarafından çağrılmış bir araç çağrısı.
    
    Örnek:
        ToolCall(
            id="call_abc123",
            tool_name="web_search",
            arguments={"query": "yapay zeka haberleri"},
            raw_text="FUNCCALL: web_search(query='yapay zeka haberleri')"
        )
    """
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    raw_text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ToolResult:
    """
    Bir araç çalıştırma sonucu.
    
    Özellikler:
        - Başarılı/başarısız durumu
        - Çıktı metni
        - Hata mesajı
        - Çalışma süresi
        - Zincirleme için metadata
    """
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    
    # Zincirleme için - bir sonraki araca aktarılacak veri
    chain_data: Optional[Dict[str, Any]] = None
    
    # Görsel çıktılar için (screenshot vb.)
    attachments: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Rapor formatında sözlük döndür"""
        return {
            "success": self.success,
            "output": str(self.output) if not isinstance(self.output, str) else self.output,
            "error": self.error,
            "execution_time": f"{self.execution_time:.3f}s",
            "tool": self.tool_name,
            "has_attachments": len(self.attachments) > 0
        }

    def __str__(self) -> str:
        if self.success:
            out = str(self.output) if self.output else "Tamamlandı"
            if len(out) > 500:
                out = out[:500] + f"\n... (çıktı {len(out)} karakter, kesildi)"
            return f"[BAŞARILI] {self.tool_name}: {out}"
        return f"[HATA] {self.tool_name}: {self.error}"


# =============================================================================
# ÖZEL İSTİSNALAR
# =============================================================================

class ToolError(Exception):
    """Araç çalıştırma hatası"""
    pass

class ToolNotFoundError(ToolError):
    """Araç bulunamadı hatası"""
    pass

class ToolExecutionError(ToolError):
    """Araç çalıştırma hatası"""
    pass

class ToolSafetyError(ToolError):
    """Güvenlik ihlali hatası"""
    pass

class ToolTimeoutError(ToolError):
    """Araç zaman aşımı hatası"""
    pass


# =============================================================================
# ARAÇ KAYIT DEFTERİ (TOOL REGISTRY)
# =============================================================================

class ToolRegistry:
    """
    Araç kayıt defteri.
    
    Tüm araçların kaydedildiği merkezi sınıf.
    Araç ekleme, silme, sorgulama ve listeleme işlemlerini yapar.
    
    Kullanım:
        registry = ToolRegistry()
        registry.register(tool)
        tool = registry.get("web_search")
        all_tools = registry.list_all()
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
    
    def register(self, tool: Tool) -> None:
        """Bir aracı kayıt defterine ekle"""
        with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"'{tool.name}' aracı zaten kayıtlı")
            
            self._tools[tool.name] = tool
            
            # Kategoriye ekle
            if tool.category not in self._categories:
                self._categories[tool.category] = []
            self._categories[tool.category].append(tool.name)
    
    def register_many(self, tools: List[Tool]) -> None:
        """Birden çok aracı toplu kaydet"""
        for tool in tools:
            self.register(tool)
    
    def unregister(self, name: str) -> None:
        """Bir aracı kayıttan sil"""
        with self._lock:
            if name not in self._tools:
                raise ToolNotFoundError(f"'{name}' aracı bulunamadı")
            
            tool = self._tools.pop(name)
            
            # Kategoriden çıkar
            if tool.category in self._categories:
                if name in self._categories[tool.category]:
                    self._categories[tool.category].remove(name)
    
    def get(self, name: str) -> Optional[Tool]:
        """İsme göre araç bul"""
        return self._tools.get(name)
    
    def get_or_raise(self, name: str) -> Tool:
        """İsme göre araç bul, yoksa hata fırlat"""
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"'{name}' isimli araç bulunamadı. Mevcut araçlar: {', '.join(self.list_names())}")
        return tool
    
    def list_all(self) -> List[Tool]:
        """Tüm araçları listele"""
        return list(self._tools.values())
    
    def list_names(self) -> List[str]:
        """Tüm araç isimlerini listele"""
        return list(self._tools.keys())
    
    def list_by_category(self, category: str) -> List[Tool]:
        """Kategoriye göre araçları listele"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Kategorileri ve içerdikleri araçları döndür"""
        result = {}
        for category, names in self._categories.items():
            result[category] = [name for name in names if name in self._tools]
        return result
    
    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """Tüm araçları OpenAI fonksiyon çağırma formatında döndür"""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    def count(self) -> int:
        """Kayıtlı araç sayısı"""
        return len(self._tools)
    
    def search(self, query: str) -> List[Tool]:
        """Araçlarda isim/açıklama araması yap"""
        query_lower = query.lower()
        results = []
        for tool in self._tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                results.append(tool)
        return results
    
    def get_dangerous_tools(self) -> List[Tool]:
        """Tehlikeli araçları listele"""
        return [t for t in self._tools.values() if t.dangerous]


# =============================================================================
# ARAÇ ÇALIŞTIRMA MOTORU (TOOL EXECUTOR)
# =============================================================================

class ToolExecutor:
    """
    Araç çalıştırma motoru.
    
    AI'dan gelen araç çağrılarını alır, güvenlik kontrollerinden geçirir
    ve ilgili handler fonksiyonunu çalıştırır.
    
    Özellikler:
        - Güvenlik kontrolü (tehlikeli araçlar için onay)
        - Zaman aşımı kontrolü
        - Hata yönetimi ve yakalama
        - Çalışma süresi ölçümü
        - Zincirleme çağrılar için veri akışı
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        default_timeout: int = 30,
        confirm_callback: Optional[Callable[[str], bool]] = None
    ):
        self.registry = registry
        self.default_timeout = default_timeout
        self.confirm_callback = confirm_callback
        
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history = 200
    
    def execute(
        self,
        tool_call: ToolCall,
        timeout: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Bir araç çağrısını çalıştır.
        
        Args:
            tool_call: Çalıştırılacak araç çağrısı
            timeout: Zaman aşımı (saniye), None = varsayılan
            context: Bağlam bilgisi (oturum kimliği vb.)
        
        Returns:
            ToolResult: Çalıştırma sonucu
        """
        start_time = time.time()
        _timeout = timeout or self.default_timeout
        
        try:
            # 1. Aracı bul
            tool = self.registry.get_or_raise(tool_call.tool_name)
            
            # 2. Güvenlik kontrolü - tehlikeli araçlar için onay iste
            if tool.dangerous or tool.requires_confirmation:
                self._check_safety(tool, tool_call.arguments)
            
            # 3. Parametreleri doğrula
            self._validate_arguments(tool, tool_call.arguments)
            
            # 4. Zaman aşımı thread'i
            result_container = []
            error_container = []
            done_event = threading.Event()
            
            def target():
                try:
                    result = tool.handler(**tool_call.arguments)
                    result_container.append(result)
                except Exception as e:
                    error_container.append(e)
                finally:
                    done_event.set()
            
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            
            # Zaman aşımını bekle
            if not done_event.wait(timeout=_timeout):
                raise ToolTimeoutError(
                    f"'{tool.name}' aracı {_timeout}s içinde tamamlanamadı"
                )
            
            # Hata varsa fırlat
            if error_container:
                raise error_container[0]
            
            # Sonucu al
            raw_result = result_container[0] if result_container else None
            
            # 5. ToolResult oluştur
            execution_time = time.time() - start_time
            
            if isinstance(raw_result, ToolResult):
                result = raw_result
                result.execution_time = execution_time
                result.tool_name = tool.name
                result.tool_call_id = tool_call.id
            else:
                result = ToolResult(
                    success=True,
                    output=raw_result,
                    execution_time=execution_time,
                    tool_name=tool.name,
                    tool_call_id=tool_call.id
                )
            
            # 6. Geçmişe ekle
            self._add_to_history(tool_call, result)
            
            return result
        
        except ToolNotFoundError as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                tool_name=tool_call.tool_name
            )
        except ToolSafetyError as e:
            return ToolResult(
                success=False,
                error=f"Güvenlik: {e}",
                execution_time=time.time() - start_time,
                tool_name=tool_call.tool_name
            )
        except ToolTimeoutError as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
                tool_name=tool_call.tool_name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                execution_time=time.time() - start_time,
                tool_name=tool_call.tool_name
            )
    
    def execute_chain(
        self,
        tool_calls: List[ToolCall],
        stop_on_error: bool = True,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Birden çok araç çağrısını zincirleme çalıştır.
        
        Her çağrının çıktısı bir sonraki çağrının context'ine eklenir.
        
        Args:
            tool_calls: Çalıştırılacak araç çağrıları listesi
            stop_on_error: Hata durumunda dur
            context: Başlangıç bağlamı
        
        Returns:
            List[ToolResult]: Tüm çağrıların sonuçları
        """
        results = []
        chain_context = dict(context or {})
        
        for i, call in enumerate(tool_calls):
            # Önceki sonucu zincirle
            if results:
                last = results[-1]
                if last.success and last.chain_data:
                    chain_context.update(last.chain_data)
            
            result = self.execute(call, context=chain_context)
            results.append(result)
            
            if not result.success and stop_on_error:
                break
        
        return results
    
    def _check_safety(self, tool: Tool, arguments: Dict[str, Any]) -> None:
        """Tehlikeli araçlar için güvenlik kontrolü"""
        if self.confirm_callback:
            arg_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
            message = (
                f"GÜVENLİK ONAYI GEREKİYOR\n"
                f"Araç: {tool.name}\n"
                f"Açıklama: {tool.description}\n"
                f"Parametreler: {arg_str}\n\n"
                f"Bu işlemi onaylıyor musunuz?"
            )
            
            if not self.confirm_callback(message):
                raise ToolSafetyError("Kullanıcı onayı gerekli")
    
    def _validate_arguments(self, tool: Tool, arguments: Dict[str, Any]) -> None:
        """Parametreleri doğrula"""
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                raise ToolExecutionError(
                    f"'{tool.name}' aracı için gerekli parametre eksik: '{param.name}'"
                )
    
    def _add_to_history(self, tool_call: ToolCall, result: ToolResult) -> None:
        """Çalıştırma geçmişine ekle"""
        self.execution_history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "tool_call": {
                "id": tool_call.id,
                "name": tool_call.tool_name,
                "arguments": tool_call.arguments
            },
            "result": {
                "success": result.success,
                "output_preview": str(result.output)[:200] if result.output else None,
                "error": result.error,
                "execution_time": result.execution_time
            }
        })
        
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Çalıştırma geçmişini getir"""
        return self.execution_history[-limit:]
    
    def clear_history(self) -> None:
        """Geçmişi temizle"""
        self.execution_history.clear()


# =============================================================================
# AI YANIT ÇÖZÜMLEYİCİ (RESPONSE PARSER)
# =============================================================================

class ResponseParser:
    """
    AI yanıtlarından araç çağrılarını çıkartır.
    
    Desteklenen formatlar:
        1. FUNCCALL: tool_name(arg1='value1', arg2='value2')
        2. <FUNCCALL>tool_name(arg1='value1')</FUNCCALL>
        3. ```tool_call\ntool_name\n{"arg1": "value1"}\n```
        4. [TOOL_CALL] {"name": "tool_name", "arguments": {...}} [/TOOL_CALL]
        5. JSON format: {"tool": "tool_name", "arguments": {...}}
    
    AI modeli hangi formatı kullanırsa kullansın,
    bu parser doğru şekilde çözümler.
    """
    
    # FUNCCALL formatı regex (iç içe parantezleri destekler)
    FUNCCALL_PATTERN = re.compile(
        r'FUNCCALL:\s*(\w+)\s*\(((?:[^()]|\([^()]*\))*)\)',
        re.IGNORECASE
    )
    
    # FUNCCALL XML etiketi (iç içe parantezleri destekler)
    XML_FUNCCALL_PATTERN = re.compile(
        r'<FUNCCALL>\s*(\w+)\s*\(((?:[^()]|\([^()]*\))*)\)\s*</FUNCCALL>',
        re.IGNORECASE
    )
    
    # JSON tool_call formatı
    JSON_TOOL_CALL_PATTERN = re.compile(
        r'\[TOOL_CALL\]\s*(\{.*?\})\s*\[/TOOL_CALL\]',
        re.IGNORECASE | re.DOTALL
    )
    
    # Code block formatı
    CODE_BLOCK_PATTERN = re.compile(
        r'```tool_call\s*\n\s*(\w+)\s*\n\s*(\{.*?\})\s*\n\s*```',
        re.IGNORECASE | re.DOTALL
    )
    
    # İç içe JSON pattern (düz JSON nesnesi)
    INLINE_JSON_PATTERN = re.compile(
        r'\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
        re.IGNORECASE | re.DOTALL
    )
    
    # Çoklu araç çağrısı ayracı
    CHAIN_SEPARATOR = re.compile(r'\n---\n|\n&&&\n', re.IGNORECASE)
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry
        self._call_counter = 0
    
    def parse(self, text) -> List[ToolCall]:
        """
        AI yanıt metninden tüm araç çağrılarını çıkart.
        
        Args:
            text: AI tarafından üretilen yanıt metni (string veya dict olabilir)
        
        Returns:
            List[ToolCall]: Bulunan tüm araç çağrıları
        """
        # Dict veya diğer tipler geldğinde string'e çevir
        if isinstance(text, dict):
            text = json.dumps(text, ensure_ascii=False)
        elif not isinstance(text, str):
            text = str(text) if text is not None else ""
        
        calls = []
        
        if not text or not text.strip():
            return calls
        
        # 1. FUNCCALL formatı
        calls.extend(self._parse_funccall(text))
        
        # 2. XML FUNCCALL formatı
        calls.extend(self._parse_xml_funccall(text))
        
        # 3. JSON TOOL_CALL formatı
        calls.extend(self._parse_json_tool_call(text))
        
        # 4. Code block formatı
        calls.extend(self._parse_code_block(text))
        
        # 5. Inline JSON formatı
        calls.extend(self._parse_inline_json(text))
        
        # Yinelenenleri temizle (aynı metin, aynı araç ismi)
        seen = set()
        unique_calls = []
        for call in calls:
            key = (call.tool_name, json.dumps(call.arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique_calls.append(call)
        
        return unique_calls
    
    def parse_single(self, text: str) -> Optional[ToolCall]:
        """
        Metinden tek bir araç çağrısı çıkart.
        Birden çok çağrı varsa ilkini döndür.
        """
        calls = self.parse(text)
        return calls[0] if calls else None
    
    def _generate_call_id(self) -> str:
        """Benzersiz çağrı kimliği oluştur"""
        self._call_counter += 1
        return f"call_{int(time.time())}_{self._call_counter}"
    
    def _parse_funccall(self, text: str) -> List[ToolCall]:
        """FUNCCALL: tool_name(arg1='value1') formatını çöz"""
        calls = []
        for match in self.FUNCCALL_PATTERN.finditer(text):
            tool_name = match.group(1)
            args_str = match.group(2).strip()
            arguments = self._parse_args_string(args_str)
            
            if tool_name and arguments is not None:
                calls.append(ToolCall(
                    id=self._generate_call_id(),
                    tool_name=tool_name,
                    arguments=arguments,
                    raw_text=match.group(0)
                ))
        return calls
    
    def _parse_xml_funccall(self, text: str) -> List[ToolCall]:
        """<FUNCCALL>tool_name(args)</FUNCCALL> formatını çöz"""
        calls = []
        for match in self.XML_FUNCCALL_PATTERN.finditer(text):
            tool_name = match.group(1)
            args_str = match.group(2).strip()
            arguments = self._parse_args_string(args_str)
            
            if tool_name and arguments is not None:
                calls.append(ToolCall(
                    id=self._generate_call_id(),
                    tool_name=tool_name,
                    arguments=arguments,
                    raw_text=match.group(0)
                ))
        return calls
    
    def _parse_json_tool_call(self, text: str) -> List[ToolCall]:
        """[TOOL_CALL] {...} [/TOOL_CALL] formatını çöz"""
        calls = []
        for match in self.JSON_TOOL_CALL_PATTERN.finditer(text):
            try:
                data = json.loads(match.group(1))
                tool_name = data.get("name") or data.get("tool")
                arguments = data.get("arguments", {})
                
                if tool_name:
                    calls.append(ToolCall(
                        id=self._generate_call_id(),
                        tool_name=tool_name,
                        arguments=arguments,
                        raw_text=match.group(0)
                    ))
            except (json.JSONDecodeError, KeyError):
                pass
        return calls
    
    def _parse_code_block(self, text: str) -> List[ToolCall]:
        """```tool_call\ntool_name\n{...}\n``` formatını çöz"""
        calls = []
        for match in self.CODE_BLOCK_PATTERN.finditer(text):
            tool_name = match.group(1).strip()
            try:
                arguments = json.loads(match.group(2))
                if tool_name and isinstance(arguments, dict):
                    calls.append(ToolCall(
                        id=self._generate_call_id(),
                        tool_name=tool_name,
                        arguments=arguments,
                        raw_text=match.group(0)
                    ))
            except json.JSONDecodeError:
                pass
        return calls
    
    def _parse_inline_json(self, text: str) -> List[ToolCall]:
        """{"tool": "...", "arguments": {...}} formatını çöz"""
        calls = []
        for match in self.INLINE_JSON_PATTERN.finditer(text):
            tool_name = match.group(1).strip()
            try:
                arguments = json.loads(match.group(2))
                if tool_name and isinstance(arguments, dict):
                    calls.append(ToolCall(
                        id=self._generate_call_id(),
                        tool_name=tool_name,
                        arguments=arguments,
                        raw_text=match.group(0)
                    ))
            except json.JSONDecodeError:
                pass
        return calls
    
    def _parse_args_string(self, args_str: str) -> Optional[Dict[str, Any]]:
        """
        Parametre string'ini sözlüğe çevir.
        
        Desteklenen formatlar:
            key='value', key="value", key=123, key=True
        """
        if not args_str or not args_str.strip():
            return {}
        
        try:
            # Önce Python literal eval dene
            # key=value, key='value', key="value" formatını dict'e çevir
            # Önce virgüllerle ayrılmış argümanları bul
            # Fakat tırnak içindeki virgülleri koru
            
            args_dict = {}
            
            # Basit regex ile anahtar=değer çiftlerini bul
            pattern = r'(\w+)\s*=\s*(\d+\.?\d*|True|False|None|"[^"]*"|\'[^\']*\')'
            for match in re.finditer(pattern, args_str):
                key = match.group(1)
                value_str = match.group(2)
                
                try:
                    value = ast.literal_eval(value_str)
                except (ValueError, SyntaxError):
                    value = value_str.strip("'\"")
                
                args_dict[key] = value
            
            # Eğer regex bulamadıysa tüm string'i tek değer olarak dene
            if not args_dict and args_str:
                # Sadece bir string argüman olabilir
                try:
                    args_dict = ast.literal_eval("{" + args_str + "}")
                except:
                    args_dict = {"value": args_str.strip("'\"")}
            
            return args_dict
        
        except Exception:
            return None
    
    def has_tool_calls(self, text) -> bool:
        """Metin arac cagrisi iceriyor mu? (dict destegi var)"""
        if isinstance(text, dict):
            text = json.dumps(text, ensure_ascii=False)
        elif not isinstance(text, str):
            text = str(text) if text is not None else ""

        if not text:
            return False
        
        patterns = [
            self.FUNCCALL_PATTERN,
            self.XML_FUNCCALL_PATTERN,
            self.JSON_TOOL_CALL_PATTERN,
            self.CODE_BLOCK_PATTERN,
            self.INLINE_JSON_PATTERN
        ]
        
        return any(p.search(text) for p in patterns)
    
    def strip_tool_calls(self, text) -> str:
        """Metinden arac cagrilarini temizle, sadece dogal dili birak (dict destegi var)"""
        if isinstance(text, dict):
            text = json.dumps(text, ensure_ascii=False)
        elif not isinstance(text, str):
            text = str(text) if text is not None else ""

        result = text
        
        # FUNCCALL temizle
        result = self.FUNCCALL_PATTERN.sub('', result)
        result = self.XML_FUNCCALL_PATTERN.sub('', result)
        result = self.JSON_TOOL_CALL_PATTERN.sub('', result)
        result = self.CODE_BLOCK_PATTERN.sub('', result)
        result = self.INLINE_JSON_PATTERN.sub('', result)
        
        # Fazla boşlukları temizle
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = result.strip()
        
        return result


# =============================================================================
# ARAÇ İŞLEYİCİLERİ (TOOL HANDLERS)
# =============================================================================

class ToolHandlers:
    """
    Tüm araç işleyici fonksiyonlarını barındıran sınıf.
    
    Her bir handler:
        - Parametre olarak **kwargs alır
        - Başarılı durumda herhangi bir değer döndürebilir
        - Hata durumunda exception fırlatabilir
    """
    
    @staticmethod
    def web_search(query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Web'de arama yapar.
        
        Mevcut web_search.py modülünü kullanır.
        """
        try:
            from web_search import get_web_search
            searcher = get_web_search()
            result = searcher.search(query, max_results=max_results)
            
            if result.get("success"):
                return {
                    "query": query,
                    "results": result.get("results", []),
                    "count": result.get("count", 0),
                    "cached": result.get("cached", False)
                }
            else:
                # Fallback: DuckDuckGo Lite
                fallback = ToolHandlers._duckduckgo_lite_search(query, max_results)
                if fallback:
                    return fallback
                
                return {"query": query, "results": [], "count": 0, "error": result.get("error")}
        
        except ImportError:
            # Web_search modülü yoksa doğrudan DuckDuckGo kullan
            return ToolHandlers._duckduckgo_lite_search(query, max_results) or {
                "query": query, "results": [], "count": 0, "error": "Arama motoru kullanılamıyor"
            }
        except Exception as e:
            return {"query": query, "results": [], "count": 0, "error": str(e)}
    
    @staticmethod
    def _duckduckgo_lite_search(query: str, max_results: int = 10) -> Optional[Dict[str, Any]]:
        """DuckDuckGo Lite API ile arama (bağımlılıksız)"""
        if not REQUESTS_OK:
            return None
        
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            
            if resp.status_code != 200:
                return None
            
            html = resp.text
            results = []
            
            for match in re.finditer(
                r'<a[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>(?:<[^>]+>)*([^<]*)',
                html, re.IGNORECASE
            ):
                url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                
                if url and not url.startswith('//'):
                    results.append({"title": title or url, "url": url, "snippet": ""})
            
            return {
                "query": query,
                "results": results[:max_results],
                "count": min(len(results), max_results),
                "source": "duckduckgo_lite"
            }
        
        except Exception:
            return None
    
    @staticmethod
    def open_app(name: str) -> Dict[str, Any]:
        """
        Uygulama başlatır.
        
        shadowcat_agent.py'deki ShadowcatApps sistemini kullanır.
        """
        try:
            from shadowcat_agent import ShadowcatApps
            return ShadowcatApps.open_app(name)
        except ImportError:
            # Fallback: start komutu
            try:
                subprocess.Popen(f'start "" "{name}"', shell=True)
                return {"success": True, "message": f"{name} başlatıldı"}
            except Exception as e:
                raise ToolExecutionError(f"Uygulama başlatılamadı: {e}")
    
    @staticmethod
    def read_file(path: str) -> Dict[str, Any]:
        """Dosya içeriğini okur."""
        try:
            expanded_path = os.path.expandvars(path)
            expanded_path = os.path.expanduser(expanded_path)
            
            if not os.path.exists(expanded_path):
                raise ToolExecutionError(f"Dosya bulunamadı: {expanded_path}")
            
            with open(expanded_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "path": expanded_path,
                "content": content,
                "size": len(content),
                "lines": content.count('\n') + 1
            }
        
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Dosya okuma hatası: {e}")
    
    @staticmethod
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """Dosyaya yazar."""
        try:
            expanded_path = os.path.expandvars(path)
            expanded_path = os.path.expanduser(expanded_path)
            
            # Dizin kontrolü
            parent = os.path.dirname(expanded_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            
            with open(expanded_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "path": expanded_path,
                "size": len(content),
                "message": f"Dosya kaydedildi: {expanded_path}"
            }
        
        except Exception as e:
            raise ToolExecutionError(f"Dosya yazma hatası: {e}")
    
    @staticmethod
    def run_code(code: str, use_subprocess: bool = False) -> Dict[str, Any]:
        """
        Python kodu çalıştırır.
        
        code_sandbox.py modülünü kullanır.
        Sandbox güvenlik kontrollerini içerir.
        """
        try:
            from code_sandbox import get_sandbox
            sandbox = get_sandbox()
            
            if use_subprocess:
                result = sandbox.execute_in_subprocess(code)
            else:
                result = sandbox.execute(code)
            
            return result
        
        except ImportError:
            # Fallback: exec ile çalıştır
            return ToolHandlers._safe_exec(code)
        except Exception as e:
            raise ToolExecutionError(f"Kod çalıştırma hatası: {e}")
    
    @staticmethod
    def _safe_exec(code: str) -> Dict[str, Any]:
        """Güvenli exec çalıştırma (fallback)"""
        import io
        import contextlib
        
        # Güvenlik filtresi — tehlikeli kalıpları engelle
        forbidden = [
            'import os', 'import subprocess', 'import sys', 'import shutil',
            '__import__', 'eval(', 'exec(', 'compile(',
            'open(', '__builtins__', 'globals()', 'locals()', 'vars(',
            'getattr(', 'setattr(', 'delattr(',
            'os.', 'subprocess.', 'sys.',
        ]
        code_lower = code.lower()
        for pattern in forbidden:
            if pattern.lower() in code_lower:
                return {
                    "success": False,
                    "error": f"Güvenlik: '{pattern}' içeren kod çalıştırılamaz"
                }
        
        output = io.StringIO()
        error = None
        
        try:
            with contextlib.redirect_stdout(output):
                exec_globals = {"__name__": "__main__", "math": math, "__builtins__": {}}
                exec(code, exec_globals)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        
        return {
            "success": error is None,
            "output": output.getvalue(),
            "error": error
        }
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """
        Sistem durumunu getirir.
        
        utils.py'deki get_system_status fonksiyonunu kullanır.
        """
        try:
            from utils import get_system_status
            return get_system_status()
        except ImportError:
            if PSUTIL_OK:
                return ToolHandlers._psutil_system_info()
            else:
                return {
                    "platform": sys.platform,
                    "python_version": sys.version.split()[0],
                    "hostname": os.environ.get("COMPUTERNAME", "Unknown"),
                    "username": os.environ.get("USERNAME", "Unknown"),
                    "note": "psutil kurulu değil, sınırlı bilgi"
                }
    
    @staticmethod
    def _psutil_system_info() -> Dict[str, Any]:
        """psutil ile sistem bilgisi al"""
        import psutil
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        now = datetime.datetime.now()
        uptime = now - boot_time
        
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        
        return {
            "platform": sys.platform,
            "hostname": os.environ.get("COMPUTERNAME", "Unknown"),
            "username": os.environ.get("USERNAME", "Unknown"),
            "uptime_days": uptime.days,
            "uptime_hours": uptime.seconds // 3600,
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_percent": ram.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "network_sent_mb": round(net.bytes_sent / (1024**2), 2),
            "network_recv_mb": round(net.bytes_recv / (1024**2), 2),
            "process_count": len(psutil.pids()),
            "python_version": sys.version.split()[0]
        }
    
    @staticmethod
    def take_screenshot(save_path: Optional[str] = None) -> Dict[str, Any]:
        """Ekran görüntüsü alır."""
        if not PYAUTOGUI_OK:
            raise ToolExecutionError("pyautogui kurulu değil, ekran görüntüsü alınamaz")
        
        try:
            if save_path is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(
                    os.path.expanduser("~"),
                    "Desktop",
                    f"screenshot_{timestamp}.png"
                )
            
            img = pyautogui.screenshot()
            img.save(save_path)
            
            return {
                "success": True,
                "path": save_path,
                "message": f"Ekran görüntüsü kaydedildi: {save_path}"
            }
        
        except Exception as e:
            raise ToolExecutionError(f"Ekran görüntüsü hatası: {e}")
    
    @staticmethod
    def send_notification(title: str, message: str, timeout: int = 5) -> Dict[str, Any]:
        """Masaüstü bildirimi gönderir."""
        if PLYER_OK:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=timeout,
                    app_name="Shadowcat AI"
                )
                return {
                    "success": True,
                    "title": title,
                    "message": message,
                    "method": "plyer"
                }
            except Exception:
                pass
        
        # Fallback: PowerShell ile bildirim
        try:
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
            $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Shadowcat AI").Show($toast)
            '''
            subprocess.run(
                ['powershell', '-NoProfile', '-Command', ps_script],
                capture_output=True, timeout=10
            )
            return {
                "success": True,
                "title": title,
                "message": message,
                "method": "powershell"
            }
        except Exception as e:
            # En basit fallback: print
            print(f"\n[BİLDİRİM] {title}: {message}\n")
            return {
                "success": True,
                "title": title,
                "message": message,
                "method": "console",
                "note": "Sadece konsola yazdırıldı"
            }
    
    @staticmethod
    def create_reminder(text: str, minutes: int) -> Dict[str, Any]:
        """
        Hatırlatıcı oluşturur.
        
        shadowcat_agent.py'deki ShadowcatNotes.add_reminder kullanır.
        """
        try:
            from shadowcat_agent import ShadowcatNotes
            return ShadowcatNotes.add_reminder(text, minutes)
        except ImportError:
            reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            
            # Hatırlatıcıyı JSON dosyasına kaydet
            reminders_file = "shadowcat_reminders.json"
            reminders = []
            
            if os.path.exists(reminders_file):
                try:
                    with open(reminders_file, 'r') as f:
                        reminders = json.load(f)
                except:
                    pass
            
            reminders.append({
                "text": text,
                "time": reminder_time.isoformat(),
                "created": datetime.datetime.now().isoformat()
            })
            
            with open(reminders_file, 'w') as f:
                json.dump(reminders, f, indent=2)
            
            # Hatırlatıcı thread'i başlat
            def reminder_worker():
                sleep_seconds = minutes * 60
                time.sleep(sleep_seconds)
                ToolHandlers.send_notification(
                    title="Shadowcat AI - Hatırlatıcı",
                    message=text
                )
            
            thread = threading.Thread(target=reminder_worker, daemon=True)
            thread.start()
            
            return {
                "success": True,
                "message": f"{minutes} dakika sonra hatırlatılacak: {text}",
                "reminder_time": reminder_time.isoformat()
            }
    
    @staticmethod
    def get_weather(city: str) -> Dict[str, Any]:
        """
        Hava durumu bilgisi getirir (gerçek API + mock).
        
        Önce OpenWeatherMap API'yi dener, yoksa mock veri döndür.
        """
        # Gerçek API denemesi
        api_key = os.environ.get("OPENWEATHER_API_KEY", "")
        if api_key and REQUESTS_OK:
            try:
                url = f"https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": city,
                    "appid": api_key,
                    "units": "metric",
                    "lang": "tr"
                }
                resp = requests.get(url, params=params, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "city": city,
                        "temperature": data["main"]["temp"],
                        "feels_like": data["main"]["feels_like"],
                        "humidity": data["main"]["humidity"],
                        "description": data["weather"][0]["description"],
                        "wind_speed": data["wind"]["speed"],
                        "country": data["sys"]["country"],
                        "source": "openweathermap"
                    }
            except Exception:
                pass
        
        # Mock veri (hata durumunda veya API anahtarı yoksa)
        import random
        conditions = ["Açık", "Parçalı Bulutlu", "Bulutlu", "Hafif Yağmurlu", "Yağmurlu", "Fırtınalı"]
        icons = ["", "", "", "", "", ""]
        idx = random.randint(0, 5)
        
        return {
            "success": True,
            "city": city,
            "temperature": round(random.uniform(5, 35), 1),
            "feels_like": round(random.uniform(3, 33), 1),
            "humidity": random.randint(30, 90),
            "description": conditions[idx],
            "icon": icons[idx],
            "wind_speed": round(random.uniform(0, 30), 1),
            "source": "mock",
            "note": "API anahtarı bulunamadı, tahmini veri gösteriliyor"
        }
    
    @staticmethod
    def calculate(expression: str) -> Dict[str, Any]:
        """
        Matematiksel ifadeyi hesaplar.
        
        Güvenli bir şekilde sadece matematik işlemlerine izin verir.
        """
        # Güvenlik: sadece izin verilen karakterler
        allowed = set("0123456789+-*/%() .,eEpisqrtabsfloorceilroundloglog10sinconstandrad")
        safe_chars = all(c in allowed for c in expression)
        
        if not safe_chars:
            raise ToolExecutionError("İfade güvenlik filtresini geçemedi: sadece matematik işlemlerine izin verilir")
        
        try:
            # Güvenli ortam
            safe_dict = {
                "math": math,
                "sqrt": math.sqrt,
                "abs": abs,
                "floor": math.floor,
                "ceil": math.ceil,
                "round": round,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "pi": math.pi,
                "e": math.e,
                "exp": math.exp,
                "radians": math.radians,
                "degrees": math.degrees
            }
            
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            
            return {
                "success": True,
                "expression": expression,
                "result": result,
                "formatted": f"{result:,.4f}" if isinstance(result, (int, float)) else str(result)
            }
        
        except Exception as e:
            raise ToolExecutionError(f"Hesaplama hatası: {e}")
    
    @staticmethod
    def translate(text: str, target_lang: str = "en") -> Dict[str, Any]:
        """
        Metni çevirir.
        
        Önce googletrans'ı dener, yoksa mock çeviri döndür.
        """
        # googletrans dene
        try:
            from googletrans import Translator
            translator = Translator()
            result = translator.translate(text, dest=target_lang)
            
            return {
                "success": True,
                "original_text": text,
                "translated_text": result.text,
                "source_lang": result.src,
                "target_lang": target_lang,
                "source": "googletrans"
            }
        except ImportError:
            pass
        except Exception:
            pass
        
        # LibreTranslate dene
        if REQUESTS_OK:
            try:
                resp = requests.post(
                    "https://libretranslate.com/translate",
                    json={"q": text, "source": "auto", "target": target_lang},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "original_text": text,
                        "translated_text": data.get("translatedText", ""),
                        "target_lang": target_lang,
                        "source": "libretranslate"
                    }
            except Exception:
                pass
        
        # Mock çeviri
        lang_names = {
            "en": "İngilizce", "fr": "Fransızca", "de": "Almanca",
            "es": "İspanyolca", "it": "İtalyanca", "ru": "Rusça",
            "zh": "Çince", "ja": "Japonca", "ar": "Arapça",
            "tr": "Türkçe"
        }
        
        lang_name = lang_names.get(target_lang, target_lang)
        
        return {
            "success": True,
            "original_text": text,
            "translated_text": f"[{lang_name} çevirisi] {text}",
            "source_lang": "auto",
            "target_lang": target_lang,
            "source": "mock",
            "note": "googletrans kurulu değil. Gerçek çeviri için 'pip install googletrans==4.0.0-rc1' çalıştırın"
        }
    
    @staticmethod
    def list_files(path: str = ".", pattern: Optional[str] = None) -> Dict[str, Any]:
        """Klasör içeriğini listeler."""
        try:
            expanded_path = os.path.expandvars(path)
            expanded_path = os.path.expanduser(expanded_path)
            
            if not os.path.exists(expanded_path):
                raise ToolExecutionError(f"Klasör bulunamadı: {expanded_path}")
            
            if not os.path.isdir(expanded_path):
                raise ToolExecutionError(f"Dizin değil: {expanded_path}")
            
            items = []
            
            for item in os.listdir(expanded_path):
                full_path = os.path.join(expanded_path, item)
                
                # Pattern filtresi
                if pattern and not re.search(pattern, item, re.IGNORECASE):
                    continue
                
                try:
                    stat = os.stat(full_path)
                    items.append({
                        "name": item,
                        "type": "dizin" if os.path.isdir(full_path) else "dosya",
                        "size": stat.st_size,
                        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
                    })
                except:
                    items.append({
                        "name": item,
                        "type": "dizin" if os.path.isdir(full_path) else "dosya",
                        "size": 0,
                        "modified": None
                    })
            
            items.sort(key=lambda x: (x["type"], x["name"].lower()))
            
            return {
                "success": True,
                "path": expanded_path,
                "items": items,
                "count": len(items),
                "directories": sum(1 for i in items if i["type"] == "dizin"),
                "files": sum(1 for i in items if i["type"] == "dosya"),
                "total_size": sum(i["size"] for i in items)
            }
        
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Listeleme hatası: {e}")
    
    @staticmethod
    def get_time() -> Dict[str, Any]:
        """Şu anki zaman ve tarihi döndürür."""
        now = datetime.datetime.now()
        return {
            "success": True,
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timestamp": now.timestamp()
        }
    
    @staticmethod
    def open_url(url: str) -> Dict[str, Any]:
        """Web tarayıcısında URL açar."""
        try:
            import webbrowser
            
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            
            webbrowser.open(url)
            
            return {
                "success": True,
                "url": url,
                "message": f"Tarayıcıda açıldı: {url}"
            }
        
        except Exception as e:
            raise ToolExecutionError(f"URL açma hatası: {e}")


# =============================================================================
# PROMPT ŞABLONU (FUNCTION CALLING PROMPT TEMPLATE)
# =============================================================================

FUNCTION_CALLING_SYSTEM_PROMPT = """# Shadowcat AI - Fonksiyon Çağırma Sistemi

Sen bir yapay zeka asistanısın. Kullanıcının isteğini yerine getirmek için aşağıdaki araçları (tools) kullanabilirsin.

## Kullanabileceğin Araçlar

{tool_descriptions}

## Nasıl Çalışır?

Bir aracı kullanmak istediğinde, yanıtının içine aşağıdaki formatlardan birini ekle:

### Format 1: FUNCCALL
```
FUNCCALL: tool_name(param1='değer1', param2='değer2')
```

### Format 2: XML
```
<FUNCCALL>tool_name(param1='değer1')</FUNCCALL>
```

### Format 3: JSON Tag
```
[TOOL_CALL] {{"name": "tool_name", "arguments": {{"param1": "değer1"}}}} [/TOOL_CALL]
```

## Önemli Kurallar

1. Her araç çağrısından SONRA aracın ne yaptığını açıkla
2. Gereksiz araç çağrısı yapma
3. Güvenlik gerektiren işlemlerde kullanıcıya danış
4. Çoklu araç çağrılarında sıralamaya dikkat et
5. Hata durumunda kullanıcıya alternatif sun

## Araç Çağırma Örnekleri

Kullanıcı: "Python'da liste nasıl ters çevrilir?"
AI: Python'da bir listeyi ters çevirmek için `reverse()` metodu veya `[::-1]` dilimleme operatörünü kullanabilirsin.

FUNCCALL: web_search(query='Python liste ters çevirme yöntemleri')

Kullanıcı: "Sistemim nasıl?"
AI: Sistem bilgilerini alıyorum, bir saniye...

FUNCCALL: get_system_info()

Sisteminiz sağlıklı görünüyor. CPU: %23, RAM: %45 kullanımda.

## Kullanıcıya Karşı Davranış

- Türkçe yanıt ver
- Arkadaş canlısı ve yardımsever ol
- Karmaşık işlemleri adım adım açıkla
- Hata durumunda çözüm öner
"""


# =============================================================================
# ANA TOOLFORMER SINIFI
# =============================================================================

class Toolformer:
    """
    Ana Toolformer sınıfı.
    
    AI ile araç sistemi arasındaki tüm entegrasyonu yönetir.
    
    Kullanım:
        tf = Toolformer()
        
        # AI yanıtını işle
        ai_response = model.generate(prompt)
        results = tf.process_response(ai_response)
        
        # Doğrudan araç çağır
        result = tf.call_tool("web_search", query="yapay zeka")
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        executor: Optional[ToolExecutor] = None,
        parser: Optional[ResponseParser] = None,
        auto_register_defaults: bool = True
    ):
        self.registry = registry or ToolRegistry()
        self.parser = parser or ResponseParser(self.registry)
        self.executor = executor or ToolExecutor(self.registry)
        
        self.parser.registry = self.registry
        
        # Varsayılan araçları kaydet
        if auto_register_defaults:
            self._register_default_tools()
        
        # İstatistikler
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_execution_time = 0.0
    
    def _register_default_tools(self) -> None:
        """Varsayılan araçları kayıt defterine ekle"""
        tools = [
            Tool(
                name="web_search",
                description="Web'de arama yapar. Güncel bilgiler, haberler ve kaynaklar için kullanılır.",
                parameters=[
                    ToolParameter(name="query", type="string", description="Arama sorgusu"),
                    ToolParameter(name="max_results", type="integer", description="Maksimum sonuç sayısı", required=False, default=10)
                ],
                handler=ToolHandlers.web_search,
                category="bilgi",
                examples=[
                    "FUNCCALL: web_search(query='yapay zeka haberleri 2026')",
                    "FUNCCALL: web_search(query='Python tkinter tutorial', max_results=5)"
                ]
            ),
            Tool(
                name="open_app",
                description="Bilgisayarda bir uygulamayı başlatır. Chrome, VSCode, Discord vb.",
                parameters=[
                    ToolParameter(name="name", type="string", description="Uygulama adı (ör: chrome, vscode, discord, notepad)")
                ],
                handler=ToolHandlers.open_app,
                category="sistem",
                examples=[
                    "FUNCCALL: open_app(name='chrome')",
                    "FUNCCALL: open_app(name='notepad')"
                ]
            ),
            Tool(
                name="read_file",
                description="Bir dosyanın içeriğini okur. Metin dosyaları için kullanılır.",
                parameters=[
                    ToolParameter(name="path", type="string", description="Dosya yolu")
                ],
                handler=ToolHandlers.read_file,
                category="dosya",
                examples=[
                    "FUNCCALL: read_file(path='C:\\\\Projects\\\\not.txt')",
                    "FUNCCALL: read_file(path='main.py')"
                ]
            ),
            Tool(
                name="write_file",
                description="Bir dosyaya metin içeriği yazar. Yeni dosya oluşturur veya varolanı günceller.",
                parameters=[
                    ToolParameter(name="path", type="string", description="Dosya yolu"),
                    ToolParameter(name="content", type="string", description="Yazılacak içerik")
                ],
                handler=ToolHandlers.write_file,
                category="dosya",
                dangerous=False,
                requires_confirmation=False,
                examples=[
                    "FUNCCALL: write_file(path='merhaba.py', content='print(\"Merhaba Dünya\")')"
                ]
            ),
            Tool(
                name="run_code",
                description="Python kodunu güvenli bir sandbox ortamında çalıştırır. Kod test etmek için kullanılır.",
                parameters=[
                    ToolParameter(name="code", type="string", description="Çalıştırılacak Python kodu"),
                    ToolParameter(name="use_subprocess", type="boolean", description="Alt süreç olarak çalıştır", required=False, default=False)
                ],
                handler=ToolHandlers.run_code,
                category="geliştirme",
                dangerous=True,
                requires_confirmation=True,
                examples=[
                    "FUNCCALL: run_code(code='print(sum(range(100)))')"
                ]
            ),
            Tool(
                name="get_system_info",
                description="Sistem bilgilerini getirir: CPU, RAM, Disk kullanımı, işletim sistemi bilgileri.",
                parameters=[],
                handler=ToolHandlers.get_system_info,
                category="sistem",
                examples=["FUNCCALL: get_system_info()"]
            ),
            Tool(
                name="take_screenshot",
                description="Ekran görüntüsü alır ve kaydeder.",
                parameters=[
                    ToolParameter(name="save_path", type="string", description="Kaydedilecek yol (opsiyonel)", required=False)
                ],
                handler=ToolHandlers.take_screenshot,
                category="sistem",
                examples=["FUNCCALL: take_screenshot()"]
            ),
            Tool(
                name="send_notification",
                description="Masaüstü bildirim gönderir. Windows bildirim alanında görünür.",
                parameters=[
                    ToolParameter(name="title", type="string", description="Bildirim başlığı"),
                    ToolParameter(name="message", type="string", description="Bildirim mesajı"),
                    ToolParameter(name="timeout", type="integer", description="Bildirim süresi (saniye)", required=False, default=5)
                ],
                handler=ToolHandlers.send_notification,
                category="sistem",
                examples=[
                    "FUNCCALL: send_notification(title='Hatırlatma', message='Toplantı zamanı!')"
                ]
            ),
            Tool(
                name="create_reminder",
                description="Bir hatırlatıcı oluşturur. Belirtilen dakika sonra bildirim gönderir.",
                parameters=[
                    ToolParameter(name="text", type="string", description="Hatırlatma metni"),
                    ToolParameter(name="minutes", type="integer", description="Kaç dakika sonra")
                ],
                handler=ToolHandlers.create_reminder,
                category="zaman",
                examples=[
                    "FUNCCALL: create_reminder(text='Proje sunumu', minutes=30)"
                ]
            ),
            Tool(
                name="get_weather",
                description="Bir şehrin hava durumu bilgisini getirir.",
                parameters=[
                    ToolParameter(name="city", type="string", description="Şehir adı")
                ],
                handler=ToolHandlers.get_weather,
                category="bilgi",
                examples=[
                    "FUNCCALL: get_weather(city='İstanbul')",
                    "FUNCCALL: get_weather(city='Ankara')"
                ]
            ),
            Tool(
                name="calculate",
                description="Matematiksel ifadeleri hesaplar. Karmaşık işlemler, trigonometri, logaritma desteği.",
                parameters=[
                    ToolParameter(name="expression", type="string", description="Matematiksel ifade")
                ],
                handler=ToolHandlers.calculate,
                category="bilgi",
                examples=[
                    "FUNCCALL: calculate(expression='2 + 2')",
                    "FUNCCALL: calculate(expression='sqrt(144) + pi * 2')"
                ]
            ),
            Tool(
                name="translate",
                description="Metni bir dilden başka bir dile çevirir. Hedef dil kodu ISO formatında (en, fr, de, es, tr, ja, zh, ru, ar).",
                parameters=[
                    ToolParameter(name="text", type="string", description="Çevrilecek metin"),
                    ToolParameter(name="target_lang", type="string", description="Hedef dil kodu (en, fr, de, es, tr, ja, zh vb.)", default="en")
                ],
                handler=ToolHandlers.translate,
                category="bilgi",
                examples=[
                    "FUNCCALL: translate(text='Merhaba dünya', target_lang='en')",
                    "FUNCCALL: translate(text='Hello world', target_lang='tr')"
                ]
            ),
            Tool(
                name="list_files",
                description="Bir dizindeki dosya ve klasörleri listeler. İsteğe bağlı desen filtresi ile.",
                parameters=[
                    ToolParameter(name="path", type="string", description="Dizin yolu", default="."),
                    ToolParameter(name="pattern", type="string", description="Dosya filtresi (regex)", required=False)
                ],
                handler=ToolHandlers.list_files,
                category="dosya",
                examples=[
                    "FUNCCALL: list_files(path='.', pattern='\\.py$')"
                ]
            ),
            Tool(
                name="get_time",
                description="Şu anki tarih ve saati döndürür.",
                parameters=[],
                handler=ToolHandlers.get_time,
                category="bilgi",
                examples=["FUNCCALL: get_time()"]
            ),
            Tool(
                name="open_url",
                description="Web tarayıcısında bir URL açar.",
                parameters=[
                    ToolParameter(name="url", type="string", description="Açılacak URL")
                ],
                handler=ToolHandlers.open_url,
                category="web",
                examples=[
                    "FUNCCALL: open_url(url='https://github.com')"
                ]
            ),
        ]
        
        self.registry.register_many(tools)
    
    def process_response(self, ai_response: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        AI yanıtını işle:
        1. Araç çağrılarını tespit et
        2. Güvenlik kontrolü yap
        3. Araçları çalıştır
        4. Sonuçları topla
        
        Args:
            ai_response: AI modelinin ürettiği yanıt metni
            context: Opsiyonel bağlam bilgisi
        
        Returns:
            Dict içeren:
                - "natural_response": Arındırılmış doğal dil yanıtı
                - "tool_calls": Tespit edilen araç çağrıları
                - "results": Çalıştırma sonuçları
                - "has_tool_calls": Araç çağrısı var mı?
                - "all_successful": Tümü başarılı mı?
                - "execution_summary": Özet bilgi
        """
        result = {
            "natural_response": ai_response,
            "tool_calls": [],
            "results": [],
            "has_tool_calls": False,
            "all_successful": True,
            "execution_summary": ""
        }
        
        # Araç çağrılarını tespit et
        tool_calls = self.parser.parse(ai_response)
        
        if not tool_calls:
            return result
        
        result["has_tool_calls"] = True
        result["tool_calls"] = [asdict(tc) for tc in tool_calls]
        
        # Doğal dil yanıtını temizle
        natural_response = self.parser.strip_tool_calls(ai_response)
        result["natural_response"] = natural_response if natural_response else "İşleminizi gerçekleştiriyorum..."
        
        # Araçları çalıştır
        execution_results = self.executor.execute_chain(tool_calls, context=context)
        result["results"] = [r.to_dict() for r in execution_results]
        
        # İstatistikler
        self.total_calls += len(tool_calls)
        for r in execution_results:
            self.total_execution_time += r.execution_time
            if r.success:
                self.successful_calls += 1
            else:
                self.failed_calls += 1
        
        # Tümü başarılı mı?
        all_successful = all(r.success for r in execution_results)
        result["all_successful"] = all_successful
        
        # Özet
        success_count = sum(1 for r in execution_results if r.success)
        fail_count = sum(1 for r in execution_results if not r.success)
        total_time = sum(r.execution_time for r in execution_results)
        
        summary_parts = [f"{len(tool_calls)} araç çağrısı işlendi"]
        if success_count:
            summary_parts.append(f"{success_count} başarılı")
        if fail_count:
            summary_parts.append(f"{fail_count} başarısız")
        summary_parts.append(f"toplam {total_time:.2f}s")
        
        result["execution_summary"] = ", ".join(summary_parts)
        
        return result
    
    def call_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Doğrudan bir aracı çağır.
        
        Args:
            tool_name: Çağrılacak araç ismi
            **kwargs: Araç parametreleri
        
        Returns:
            ToolResult: Çalıştırma sonucu
        """
        tool_call = ToolCall(
            id=self.parser._generate_call_id(),
            tool_name=tool_name,
            arguments=kwargs,
            raw_text=f"FUNCCALL: {tool_name}({kwargs})"
        )
        
        return self.executor.execute(tool_call)
    
    def build_system_prompt(self, include_descriptions: bool = True) -> str:
        """
        AI modeli için sistem prompt'u oluşturur.
        
        Args:
            include_descriptions: Araç açıklamalarını dahil et
        
        Returns:
            str: Sistem prompt metni
        """
        if not include_descriptions:
            return FUNCTION_CALLING_SYSTEM_PROMPT.format(tool_descriptions="")
        
        # Araç açıklamalarını formatla
        descriptions = []
        for tool in self.registry.list_all():
            params_str = ", ".join(
                f"{p.name}: {p.type}" + (" (gerekli)" if p.required else " (opsiyonel)")
                for p in tool.parameters
            )
            
            danger = " [TEHLIKELI]" if tool.dangerous else ""
            desc = f"### {tool.name}{danger}\n{tool.description}\nParametreler: {params_str}"
            
            if tool.examples:
                desc += "\nÖrnek: " + tool.examples[0]
            
            descriptions.append(desc)
        
        tool_descriptions = "\n\n".join(descriptions)
        
        return FUNCTION_CALLING_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)
    
    def get_stats(self) -> Dict[str, Any]:
        """Toolformer istatistiklerini getir"""
        return {
            "registered_tools": self.registry.count(),
            "categories": list(self.registry.get_categories().keys()),
            "dangerous_tools": [t.name for t in self.registry.get_dangerous_tools()],
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_execution_time": f"{self.total_execution_time:.2f}s",
            "success_rate": f"{(self.successful_calls / max(self.total_calls, 1)) * 100:.1f}%"
        }
    
    def add_tool(self, tool: Tool) -> None:
        """Yeni bir araç ekle"""
        self.registry.register(tool)
    
    def remove_tool(self, name: str) -> None:
        """Bir aracı kaldır"""
        self.registry.unregister(name)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Araç bilgilerini getir"""
        return self.registry.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Kayıtlı araçları listele"""
        if category:
            tools = self.registry.list_by_category(category)
        else:
            tools = self.registry.list_all()
        
        return [t.to_dict() for t in tools]
    
    def reset(self) -> None:
        """İstatistikleri sıfırla"""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_execution_time = 0.0
        self.executor.clear_history()


# =============================================================================
# KULLANIM ÖRNEKLERİ
# =============================================================================

def demo():
    """Toolformer'ı test etmek için demo fonksiyonu"""
    print("=" * 60)
    print("  TOOLFORMER - Shadowcat AI Fonksiyon Çağırma Sistemi")
    print("=" * 60)
    
    tf = Toolformer()
    
    print(f"\n[KAYITLI ARAC]: {tf.registry.count()}")
    print(f"[KATEGORI]: {', '.join(tf.registry.get_categories().keys())}")
    print(f"[TEHLIKELI]: {', '.join(t.name for t in tf.registry.get_dangerous_tools())}")
    
    print("\n" + "=" * 60)
    print("  ORNEK KULLANIMLAR")
    print("=" * 60)
    
    # Ornek 1: Sistem bilgisi
    print("\n[Ornek 1] Sistem bilgisi sorgulama")
    print("   AI: 'Sistem durumumu kontrol eder misin?'")
    print("   AI Response: 'Tabi, hemen bakiyorum...")
    print("   FUNCCALL: get_system_info()")
    print("   Sistem saglikli gorunuyor.'")
    
    result = tf.process_response(
        "Tabii, hemen bakiyorum...\nFUNCCALL: get_system_info()\nSistem saglikli gorunuyor."
    )
    for r in result["results"]:
        status = "[OK]" if r["success"] else "[HATA]"
        print(f"   {status} {r.get('tool', '?')}: {r.get('execution_time', '?')}")
    
    # Ornek 2: Web arama
    print("\n[Ornek 2] Web arama")
    print("   AI: 'En son teknoloji haberlerini arastiriyorum...'")
    print("   FUNCCALL: web_search(query='teknoloji haberleri 2026')")
    
    result = tf.process_response(
        "En son teknoloji haberlerini arastiriyorum...\nFUNCCALL: web_search(query='teknoloji haberleri 2026', max_results=5)"
    )
    for r in result["results"]:
        status = "[OK]" if r["success"] else "[HATA]"
        print(f"   {status} {r.get('tool', '?')}: {r.get('execution_time', '?')}")
        if r["success"]:
            data = r.get("output", "{}")
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    pass
            if isinstance(data, dict):
                count = data.get("count", 0)
                print(f"      -> {count} sonuc bulundu")
    
    # Ornek 3: Hesaplama
    print("\n[Ornek 3] Matematiksel hesaplama")
    print("   AI: 'Hemen hesapliyorum...'")
    print("   FUNCCALL: calculate(expression='2 ** 10 + sqrt(144) * pi')")
    
    result = tf.process_response(
        "Hemen hesapliyorum...\nFUNCCALL: calculate(expression='2 ** 10 + sqrt(144) * pi')"
    )
    for r in result["results"]:
        status = "[OK]" if r["success"] else "[HATA]"
        print(f"   {status} {r.get('tool', '?')}: {r.get('execution_time', '?')}")
        if r["success"]:
            print(f"      -> Sonuc: {r.get('output', '?')}")
    
    # Istatistikler
    print("\n" + "=" * 60)
    print("  ISTATISTIKLER")
    print("=" * 60)
    stats = tf.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\nDemo tamamlandi!\n")


# =============================================================================
# ANA ÇALIŞTIRMA
# =============================================================================

if __name__ == "__main__":
    demo()
