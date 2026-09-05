# -*- coding: utf-8 -*-
"""Dropdown ve bildirimlerden emojileri kaldirir."""
import io

p = "web/templates/chat.html"
s = io.open(p, encoding="utf-8").read()

deg = [
    ("🐾 SHADOWCAT AİLESİ", "SHADOWCAT AİLESİ"),
    ("🐾 GCM+ (Shadowcat 3B)", "GCM+ (Shadowcat 3B)"),
    ("✅ ŞU AN CEVAP VEREN", "ŞU AN CEVAP VEREN"),
    ("🧠 Atlas", "Atlas"),
    ("💻 CodeS", "CodeS"),
    ("🔮 NeoS", "NeoS"),
    ("⚡ Lynx", "Lynx"),
    ("📖 Sphynx", "Sphynx"),
    ("🛡️ Aegis", "Aegis"),
    ("🎨 SkyS-Maker", "SkyS-Maker"),
    ("🔊 Echo", "Echo"),
    ("👑 MaxCode", "MaxCode"),
    ("🧠 DeepSeek-R1 14B", "DeepSeek-R1 14B"),
    ("💻 Qwen-Coder 14B", "Qwen-Coder 14B"),
    ("⚡ Effort", "Effort"),
    ("🧠 Thinking", "Thinking"),
    ("🐢 Düşük", "Düşük"),
    ("🔥 Orta", "Orta"),
    ("👑 Yüksek", "Yüksek"),
    ("🧠 Maksimum", "Maksimum"),
    ("⚠️ daha fazla kullanım", "daha fazla kullanım"),
    ("🚧 ' + name + ' yakında geliyor — 🐾 GCM+ cevap veriyor", "' + name + ' yakında geliyor — GCM+ cevap veriyor"),
    ("toast('⚡ Effort: '", "toast('Effort: '"),
    ("'🧠 Thinking: AÇIK'", "'Thinking: AÇIK'"),
    ("'🧠 Thinking: KAPALI'", "'Thinking: KAPALI'"),
    ("'🐾 GCM+'", "'GCM+'"),
    ("🐾 GCM+ cevap veriyor", "GCM+ cevap veriyor"),
    ("'🐾 Max+'", "'Max+'"),
    ("'🧠 R1 14B'", "'R1 14B'"),
    ("'💻 Coder 14B'", "'Coder 14B'"),
    ("⚡ EFFORT", "EFFORT"),
    ("⚡ Lite", "Lite"),
    ("🔥 Flash", "Flash"),
    ("👑 Pro", "Pro"),
    ("🧠 Expert", "Expert"),
    ("🧠 Düşünme modu: AÇIK (effort yüksek)", "Düşünme modu: AÇIK (effort yüksek)"),
    ("⚡ Düşünme modu: KAPALI (effort düşük)", "Düşünme modu: KAPALI (effort düşük)"),
]
say = 0
for eski, yeni in deg:
    if eski in s:
        say += s.count(eski)
        s = s.replace(eski, yeni)

io.open(p, "w", encoding="utf-8", newline="").write(s)
print(f"OK: {say} emoji kaldirildi (dropdown + bildirimler)")

# codes_router etiketleri
p2 = "codes_router.py"
s2 = io.open(p2, encoding="utf-8").read()
s2 = s2.replace('"🐾 Max+ (Yerli)"', '"Max+ (Yerli)"')
io.open(p2, "w", encoding="utf-8", newline="").write(s2)
print("OK: codes_router etiketleri temizlendi")
