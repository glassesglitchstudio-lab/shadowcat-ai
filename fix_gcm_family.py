# -*- coding: utf-8 -*-
"""Model listesi: GCM+ aktif + 9 aile uyesi 'Yakinda' rozetli + otomatik GCM+ fallback."""
import io

p = "web/templates/chat.html"
s = io.open(p, encoding="utf-8").read()

soon = '<span style="background:rgba(255,180,84,.15);color:#e8a33d;border:1px solid rgba(255,180,84,.3);padding:1px 6px;border-radius:4px;font-size:10px;margin-left:6px">Yakında</span>'

# ---- 1) Dropdown model listesi: GCM+ aktif + aile kadrosu Yakinda
eski = '''                    <div style="padding:6px 12px 2px;font-size:.6rem;font-weight:700;color:#999;letter-spacing:.06em">MODEL SEÇ</div>
                    <div class="model-opt active" onclick="selectModel('CODES')">💻 CodeS<span class="sub">tek model + XLoRA uzmanları — ana beyin</span></div>
                    <div class="model-opt" onclick="selectModel('MAXP')">🐾 Max+ (Yerli 3B)<span class="sub">en hızlı — gulmezcetiner:max+ ✅</span></div>
                    <div class="model-opt" onclick="selectModel('R1_14B')">🧠 DeepSeek-R1 14B<span class="sub">adım adım düşünür ✅</span></div>
                    <div class="model-opt" onclick="selectModel('CODER_14B')">💻 Qwen-Coder 14B<span class="sub">derin kod ✅</span></div>
                    <div style="border-top:1px solid #eee;margin:6px 0"></div>'''
yeni = '''                    <div style="padding:6px 12px 2px;font-size:.6rem;font-weight:700;color:#999;letter-spacing:.06em">🐾 SHADOWCAT AİLESİ</div>
                    <div class="model-opt active" onclick="selectModel('MAXP')">🐾 GCM+ (Shadowcat 3B)<span class="sub">✅ ŞU AN CEVAP VEREN — gulmezcetiner:max+ · hızlı ve çevik</span></div>
                    <div class="model-opt" onclick="selectComing('Atlas 3B')">🧠 Atlas<span class="sub">ana asistan — marka yüzü</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('CodeS 14B')">💻 CodeS<span class="sub">kod — 6 XLoRA uzmanı</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('NeoS 30B')">🔮 NeoS<span class="sub">derin muhakeme — düşünce izleri</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('Lynx 1.5B')">⚡ Lynx<span class="sub">saniye altı hız — Elytra motoru</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('Sphynx 7B')">📖 Sphynx<span class="sub">hafıza + RAG ustası</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('Aegis 7B')">🛡️ Aegis<span class="sub">güvenlik muhafızı</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('SkyS-Maker 7B')">🎨 SkyS-Maker<span class="sub">görsel üretim</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('Echo 3B')">🔊 Echo<span class="sub">ses — kediyle konuşma</span>''' + soon + '''</div>
                    <div class="model-opt" onclick="selectComing('MaxCode 24B')">👑 MaxCode<span class="sub">yetkili admin modeli</span>''' + soon + '''</div>
                    <div style="border-top:1px solid #eee;margin:6px 0"></div>
                    <div style="padding:6px 12px 2px;font-size:.6rem;font-weight:700;color:#999;letter-spacing:.06em">MOTORLAR (Yardımcılar — CodeS zincirinde)</div>
                    <div class="model-opt" onclick="selectModel('R1_14B')">🧠 DeepSeek-R1 14B<span class="sub">adım adım düşünür ✅</span></div>
                    <div class="model-opt" onclick="selectModel('CODER_14B')">💻 Qwen-Coder 14B<span class="sub">derin kod ✅</span></div>
                    <div style="border-top:1px solid #eee;margin:6px 0"></div>'''
assert eski in s, "model listesi bulunamadi"
s = s.replace(eski, yeni, 1)

# ---- 2) DİĞER bölümünü kaldir (aile listesi kapsadi)
eski = '''                    <div style="border-top:1px solid #eee;margin:6px 0"></div>
                    <div style="padding:8px 12px 2px;font-size:.6rem;font-weight:700;color:#999;letter-spacing:.06em">DİĞER</div>
                    <div class="model-opt" onclick="toast('🎨 SkyS-Maker beta yolda — plan B1')" style="opacity:.55">🎨 SkyS-Maker<span class="sub">🔧 yapılacak — görsel üretim</span></div>'''
if eski in s:
    s = s.replace(eski, "", 1)

# ---- 3) selectComing fonksiyonu + varsayilan GCM+
eski = "        currentModel = 'MAXP';\n"
yeni = """        currentModel = 'MAXP';
    }
    // 'Yakında' modeli seçilirse: GCM+ devreye girer (Shadowcat her zaman cevap verir)
    function selectComing(name) {
        currentModel = 'MAXP';
        const mEl = document.getElementById('modelName');
        const sEl = document.getElementById('sidebarModel');
        if (mEl) mEl.textContent = '🐾 GCM+';
        if (sEl) sEl.textContent = '🐾 GCM+';
        document.querySelectorAll('.model-opt').forEach(o => o.classList.remove('active'));
        toast('🚧 ' + name + ' yakında geliyor — 🐾 GCM+ cevap veriyor');
    }
    function _selectComing_dummy() {
"""
# dikkat: selectModel govdesinin kapanmasi bozulmasin — bu yapiyi degistirmek yerine
# selectComing'i ayri fonksiyon olarak ekleyecegiz (asagida), yukaridaki tasarim iptal.
yeni = "        currentModel = 'MAXP';\n"
s = s.replace(eski, yeni, 1)

# selectComing'i ayri fonksiyon olarak ekle (selectModel'den once)
eski = "    function selectModel(id) {"
yeni = """    function selectComing(name) {
        currentModel = 'MAXP';
        toast('🚧 ' + name + ' yakında geliyor — 🐾 GCM+ cevap veriyor');
    }

    function selectModel(id) {"""
assert eski in s, "selectModel yok"
s = s.replace(eski, yeni, 1)

# ---- 4) varsayilan etiketler: GCM+
s = s.replace('<span id="modelName">💻 CodeS</span>', '<span id="modelName">🐾 GCM+</span>')
s = s.replace('<span id="sidebarModel">💻 CodeS</span>', '<span id="sidebarModel">🐾 GCM+</span>')
s = s.replace("let currentModel = 'CODES';", "let currentModel = 'MAXP';")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("OK: GCM+ aktif + 9 aile uyesi Yakinda rozetli + selectComing fallback")
