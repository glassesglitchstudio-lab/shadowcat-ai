"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║       MCP BRIDGE - Model Context Protocol                 ║
║                                                               ║
║     Shadowcat AI'yı MCP ekosistemine bağlar                 ║
║                                                               ║
║     Özellikler:                                               ║
║     - MCP Server: Shadowcat araçlarını MCP üzerinden aç     ║
║     - MCP Client: Dış MCP sunucularına bağlan                ║
║     - Tool dönüşümü: Shadowcat <-> MCP tool format          ║
║     - JSON-RPC over HTTP/SSE                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import json
import logging
import uuid
import requests
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger("MCPBridge")

# ─────────────────────────────────────────────────────────────
# SABİTLER
# ─────────────────────────────────────────────────────────────

MCP_VERSION = "2025-03-26"
JSON_RPC_VERSION = "2.0"

# ─────────────────────────────────────────────────────────────
# VERİ SINIFLARI
# ─────────────────────────────────────────────────────────────

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict = field(default_factory=lambda: {"type": "object", "properties": {}, "required": []})

@dataclass
class MCPResource:
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"

@dataclass
class MCPPrompt:
    name: str
    description: str = ""
    arguments: List[Dict] = field(default_factory=list)

@dataclass
class MCPServerConfig:
    name: str = "shadowcat-mcp"
    version: str = "1.0.0"
    transport: str = "http"  # http, sse

# ─────────────────────────────────────────────────────────────
# MCP SUNUCU
# ─────────────────────────────────────────────────────────────

class MCPServer:
    """Shadowcat araçlarını MCP protokolüyle dışarıya açar."""

    def __init__(self, core=None, config: MCPServerConfig = None):
        self.core = core
        self.config = config or MCPServerConfig()
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}
        self._running = False
        self._server_thread = None

    def register_tool(self, tool: MCPTool):
        self._tools[tool.name] = tool

    def register_resource(self, resource: MCPResource):
        self._resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPrompt):
        self._prompts[prompt.name] = prompt

    def load_from_core(self):
        """Shadowcat Core'daki tüm araçları MCP tool'larına dönüştür."""
        if not self.core or not self.core.toolformer:
            return
        try:
            for tool in self.core.toolformer.registry.list_all():
                params = {}
                required = []
                for p in tool.parameters:
                    ptype = "string"
                    if p.type == "integer" or p.type == "number":
                        ptype = p.type
                    elif p.type == "boolean":
                        ptype = "boolean"
                    params[p.name] = {
                        "type": ptype,
                        "description": p.description or ""
                    }
                    if p.required if hasattr(p, 'required') else True:
                        required.append(p.name)

                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema={
                        "type": "object",
                        "properties": params,
                        "required": required
                    }
                )
                self.register_tool(mcp_tool)

            logger.info(f"MCP: {len(self._tools)} tool yüklendi")
        except Exception as e:
            logger.warning(f"MCP tool yükleme hatası: {e}")

    # ── JSON-RPC Handlers ──

    def handle_request(self, body: Dict) -> Dict:
        """Gelen JSON-RPC isteğini işle."""
        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id", str(uuid.uuid4()))

        handlers = {
            "ping": self._handle_ping,
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
        }

        handler = handlers.get(method)
        if not handler:
            return self._error(req_id, -32601, f"Method bulunamadı: {method}")

        try:
            result = handler(params)
            return {"jsonrpc": JSON_RPC_VERSION, "id": req_id, "result": result}
        except Exception as e:
            logger.error(f"MCP handler hatası ({method}): {e}")
            return self._error(req_id, -32603, str(e))

    def _handle_ping(self, params):
        return {"version": MCP_VERSION, "timestamp": datetime.now().isoformat()}

    def _handle_initialize(self, params):
        return {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {}
            },
            "serverInfo": {
                "name": self.config.name,
                "version": self.config.version
            }
        }

    def _handle_tools_list(self, params):
        cursor = params.get("cursor")
        tools_list = [asdict(t) for t in self._tools.values()]
        result = {"tools": tools_list}
        if cursor:
            result["nextCursor"] = None
        return result

    def _handle_tools_call(self, params):
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if name not in self._tools:
            raise ValueError(f"Tool bulunamadı: {name}")
        if not self.core or not self.core.toolformer:
            raise RuntimeError("Toolformer aktif değil")
        result = self.core.call_tool(name, **arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, default=str)
                }
            ]
        }

    def _handle_resources_list(self, params):
        return {"resources": [asdict(r) for r in self._resources.values()]}

    def _handle_resources_read(self, params):
        uri = params.get("uri", "")
        resource = self._resources.get(uri)
        if not resource:
            raise ValueError(f"Resource bulunamadı: {uri}")
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": resource.mime_type,
                    "text": f"Resource: {resource.name}"
                }
            ]
        }

    def _handle_prompts_list(self, params):
        return {"prompts": [asdict(p) for p in self._prompts.values()]}

    def _error(self, req_id, code, message):
        return {
            "jsonrpc": JSON_RPC_VERSION,
            "id": req_id,
            "error": {"code": code, "message": message}
        }

    # ── HTTP Transport ──

    def start_http(self, host="127.0.0.1", port=8766):
        """Flask ile MCP HTTP sunucusu başlat."""
        try:
            from flask import Flask, request, jsonify
            app = Flask(f"MCP_{self.config.name}")

            @app.route("/mcp", methods=["POST"])
            def mcp_handler():
                body = request.get_json(force=True, silent=True)
                if not body:
                    return jsonify(self._error(None, -32700, "Parse hatası")), 400
                response = self.handle_request(body)
                return jsonify(response)

            @app.route("/mcp/health", methods=["GET"])
            def health():
                return jsonify({"status": "ok", "tools": len(self._tools)})

            logger.info(f"MCP Server başlatıldı: http://{host}:{port}/mcp")
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except ImportError:
            logger.error("Flask yüklü değil, MCP HTTP server başlatılamadı")

    def start(self, host="127.0.0.1", port=8766):
        """MCP sunucusunu arka planda başlat."""
        if self._running:
            return
        self._running = True
        self._server_thread = threading.Thread(
            target=self.start_http, args=(host, port), daemon=True
        )
        self._server_thread.start()
        logger.info(f"MCP Bridge: {self.config.name} v{self.config.version} aktif")


# ─────────────────────────────────────────────────────────────
# MCP İSTEMCİ
# ─────────────────────────────────────────────────────────────

class MCPClient:
    """Harici MCP sunucularına bağlanır ve araçlarını kullanır."""

    def __init__(self):
        self._servers: Dict[str, Dict] = {}

    def connect(self, name: str, url: str) -> bool:
        """Bir MCP sunucusuna bağlan."""
        try:
            resp = requests.post(
                f"{url}/mcp",
                json={"jsonrpc": JSON_RPC_VERSION, "method": "initialize", "id": "init"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data:
                    self._servers[name] = {"url": url, "info": data["result"]}
                    logger.info(f"MCP bağlantı: {name} @ {url}")
                    return True
            logger.warning(f"MCP bağlantı hatası {url}: {resp.status_code}")
            return False
        except Exception as e:
            logger.warning(f"MCP bağlantı hatası ({name}): {e}")
            return False

    def list_tools(self, server_name: str) -> List[Dict]:
        """Bir sunucudaki tool'ları listele."""
        server = self._servers.get(server_name)
        if not server:
            return []
        try:
            resp = requests.post(
                f"{server['url']}/mcp",
                json={"jsonrpc": JSON_RPC_VERSION, "method": "tools/list", "id": "1"},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.warning(f"MCP tools list hatası ({server_name}): {e}")
        return []

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict = None) -> Dict:
        """Bir sunucuda tool çağır."""
        server = self._servers.get(server_name)
        if not server:
            return {"error": f"Sunucu bulunamadı: {server_name}"}
        try:
            resp = requests.post(
                f"{server['url']}/mcp",
                json={
                    "jsonrpc": JSON_RPC_VERSION,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments or {}},
                    "id": "1"
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json().get("result", {})
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def list_all_tools(self) -> List[Dict]:
        """Tüm bağlı sunuculardaki tool'ları topla."""
        all_tools = []
        for name in self._servers:
            tools = self.list_tools(name)
            for t in tools:
                t["_server"] = name
            all_tools.extend(tools)
        return all_tools

    def get_connected_servers(self) -> List[str]:
        return list(self._servers.keys())

    def disconnect(self, name: str):
        self._servers.pop(name, None)


# ─────────────────────────────────────────────────────────────
# MCP BRIDGE (SERVER + CLIENT)
# ─────────────────────────────────────────────────────────────

class MCPBridge:
    """MCP Server + Client'ı birleştiren ana köprü."""

    def __init__(self, core=None):
        self.core = core
        self.server = MCPServer(core=core)
        self.client = MCPClient()
        self._initialized = False

    def initialize(self, host="127.0.0.1", port=8766):
        """MCP Bridge'i başlat: server'ı yükle + client'ı hazırla."""
        if self._initialized:
            return
        self.server.load_from_core()
        self.server.start(host=host, port=port)
        self._initialized = True

    def get_status(self) -> Dict:
        return {
            "server_running": self.server._running,
            "tools_served": len(self.server._tools),
            "connected_servers": self.client.get_connected_servers(),
            "external_tools": len(self.client.list_all_tools())
        }


# Singleton
_mcp_instance = None

def get_mcp_bridge(core=None):
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = MCPBridge(core=core)
    return _mcp_instance
