from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("routes.mcp")
router = APIRouter()

def get_bridge():
    try:
        from mcp_bridge import get_mcp_bridge
        from shadowcat_core import get_core
        core = get_core()
        bridge = get_mcp_bridge(core=core)
        return bridge
    except Exception as e:
        logger.warning(f"MCP Bridge yüklenemedi: {e}")
        return None

class MCPConnectRequest(BaseModel):
    name: str
    url: str

class MCPToolCallRequest(BaseModel):
    server: str
    tool: str
    arguments: Optional[Dict[str, Any]] = None

@router.get("/status")
async def mcp_status():
    bridge = get_bridge()
    if not bridge:
        return {"available": False, "error": "MCP Bridge yüklü değil"}
    bridge.initialize()
    return {
        "available": True,
        "status": bridge.get_status()
    }

@router.post("/connect")
async def mcp_connect(req: MCPConnectRequest):
    bridge = get_bridge()
    if not bridge:
        raise HTTPException(status_code=503, detail="MCP Bridge yüklü değil")
    bridge.initialize()
    success = bridge.client.connect(req.name, req.url)
    if not success:
        raise HTTPException(status_code=400, detail=f"Bağlantı başarısız: {req.url}")
    return {"success": True, "server": req.name, "url": req.url}

@router.get("/servers")
async def mcp_servers():
    bridge = get_bridge()
    if not bridge:
        return {"servers": []}
    bridge.initialize()
    return {"servers": bridge.client.get_connected_servers()}

@router.get("/tools")
async def mcp_tools(server: Optional[str] = None):
    bridge = get_bridge()
    if not bridge:
        return {"tools": []}
    bridge.initialize()
    if server:
        tools = bridge.client.list_tools(server)
    else:
        tools = bridge.client.list_all_tools()
    return {"tools": tools, "count": len(tools)}

@router.post("/call")
async def mcp_call_tool(req: MCPToolCallRequest):
    bridge = get_bridge()
    if not bridge:
        raise HTTPException(status_code=503, detail="MCP Bridge yüklü değil")
    bridge.initialize()
    result = bridge.client.call_tool(req.server, req.tool, req.arguments or {})
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"success": True, "result": result}

@router.post("/disconnect")
async def mcp_disconnect(req: MCPConnectRequest):
    bridge = get_bridge()
    if not bridge:
        return {"success": False, "error": "MCP Bridge yüklü değil"}
    bridge.client.disconnect(req.name)
    return {"success": True, "server": req.name}
