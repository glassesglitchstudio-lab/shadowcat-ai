# -*- coding: utf-8 -*-
"""
Shadowcat Export - sohbet geçmisini disa aktarma (JSON/MD/HTML)
Kullanicilar konusmalarini kaydedebilir, paylasabilir.
"""
import json, time, html as html_mod
from typing import List, Dict
from pathlib import Path


def export_json(messages: List[Dict]) -> str:
    """JSON formatinda disa aktar"""
    return json.dumps({"exported_at": time.strftime("%Y-%m-%d %H:%M:%S"), "messages": messages},
                      ensure_ascii=False, indent=2)


def export_markdown(messages: List[Dict], title: str = "Shadowcat Sohbeti") -> str:
    """Markdown formatinda disa aktar"""
    lines = [f"# {title}", "", f"*Disa aktarildi: {time.strftime('%Y-%m-%d %H:%M:%S')}*", ""]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        label = "Kullanici" if role == "user" else "Shadowcat"
        lines.append(f"## {label}\n\n{content}\n")
    return "\n".join(lines)


def export_html(messages: List[Dict], title: str = "Shadowcat Sohbeti") -> str:
    """HTML formatinda disa aktar (kopyala-yapistir)"""
    css = """
    <style>
      body{font-family:sans-serif;max-width:720px;margin:20px auto;padding:20px;background:#f7f5f0;color:#222}
      h1{color:#7c3aed}
      .msg{background:#fff;border:1px solid #e0ddd5;border-radius:10px;padding:12px 16px;margin:10px 0}
      .user{background:#f0efe8}
      .sc{border-left:3px solid #7c3aed}
      .t{font-size:.75rem;color:#999}
    </style>
    """
    body = [f"<h1>{html_mod.escape(title)}</h1>", "<p class='t'>" + time.strftime("%Y-%m-%d %H:%M:%S") + "</p>"]
    for m in messages:
        role = m.get("role", "user")
        content = html_mod.escape(m.get("content", "")).replace("\n", "<br>")
        cls = "user" if role == "user" else "sc"
        label = "Kullanici" if role == "user" else "Shadowcat"
        body.append(f"<div class='msg {cls}'><b>{label}</b><br>{content}</div>")
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'>{css}</head><body>{''.join(body)}</body></html>"


def export_file(messages: List[Dict], format: str = "json", title: str = "Shadowcat Sohbeti") -> Dict:
    """Disari aktarma iste - dosya yolu ve icerik doner"""
    format = format.lower()
    if format == "md" or format == "markdown":
        return {"filename": f"shadowcat_sohbet_{int(time.time())}.md", "content": export_markdown(messages, title)}
    if format == "html":
        return {"filename": f"shadowcat_sohbet_{int(time.time())}.html", "content": export_html(messages, title)}
    return {"filename": f"shadowcat_sohbet_{int(time.time())}.json", "content": export_json(messages)}


if __name__ == "__main__":
    test = [
        {"role": "user", "content": "Merhaba!"},
        {"role": "assistant", "content": "Selam, nasil yardimci olabilirim?"},
    ]
    print(export_file(test, "md", "Test")["content"][:200])