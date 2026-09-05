# -*- coding: utf-8 -*-
"""Cache-bust + sahte cevap temizligi."""
import io

# ---- 1) chat.html: sahte R1 mesajini sil -> non-stream ile bir kez daha dene
p = "web/templates/chat.html"
s = io.open(p, encoding="utf-8").read()
eski = """        typer.flush();

        if (!full || !full.trim()) {
            full = "**[👑 ShadowCat-R1 14B]**: Ben **Elytra-ai** tarafından özel olarak eğitilmiş **ShadowCat-R1 14B Amiral Gemisi** yapay zeka modeliyim! 7/24 kesintisiz hizmetinizdeyim. 🐱⚡";
        }"""
yeni = """        typer.flush();

        if (!full || !full.trim()) {
            // Akis bos döndüyse kanitlanmis non-stream yolu bir kez daha dene
            try { full = await callChat(msg); } catch (e) { full = ''; }
            if (!full || !full.trim()) {
                full = "[Hata] Yerel sunucu yanit vermedi. 'sunucu.bat' ile baslatip tekrar deneyin.";
            }
        }"""
assert eski in s, "sahte mesaj bulunamadi"
s = s.replace(eski, yeni, 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("OK: sahte cevap silindi -> callChat yedegi eklendi")

# ---- 2) main.py: / ve /app cevaplarina cache-header (tarayici hep taze UI yuklesin)
p2 = "main.py"
s2 = io.open(p2, encoding="utf-8").read()
eski2 = '''        return templates.TemplateResponse(

            request=request,

            name="chat.html",

            context={"request": request}

        )'''
yeni2 = '''        return templates.TemplateResponse(

            request=request,

            name="chat.html",

            context={"request": request},

            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}

        )'''
assert eski2 in s2, "kok rota bulunamadi"
s2 = s2.replace(eski2, yeni2, 1)

eski3 = 'return FileResponse(os.path.join(BASE_DIR, "web", "templates", "app.html"))'
yeni3 = ('return FileResponse(os.path.join(BASE_DIR, "web", "templates", "app.html"), '
         'headers={"Cache-Control": "no-cache, no-store, must-revalidate"})')
assert eski3 in s2, "app rota bulunamadi"
s2 = s2.replace(eski3, yeni3, 1)
io.open(p2, "w", encoding="utf-8", newline="").write(s2)
print("OK: / ve /app cache-header eklendi")
