# -*- coding: utf-8 -*-
"""codeS_kod_lora pilot dataset builder.

Bilesim (SHT_PLANI + CODES_ROUTER_PLAN):
  - CodeAlpaca_20K alt kumesi (HF streaming) ................ ~2500
  - codeS kimlik/persona paketi (kendini tanitma) ........... ~150
  - Turkce kod soru-cevap paketi (el yazimi kaliteli) ....... ~150
Cikti: opti-lora/data/codes_kod_lora.jsonl  (SFTTrainer "text" alanli)
"""
import itertools
import json
import os
import random

CIKTI = r"C:\Users\ErCuM\CascadeProjects\shadowcat\opti-lora\data\codes_kod_lora.jsonl"
CODES_LIMIT = 2500
PERSONA_LIMIT = 150
TR_LIMIT = 150

SYSTEM = ("Sen CodeS'sin - Elytra-ai tarafindan gelistirilen kod yazma ve yazilim "
          "muhendisligi uzmani model. Turkce ve Ingilizce sorulara net cevap verirsin. "
          "Kod bloklarini dil etiketiyle yazarsin. Doğrudan cozume odaklanırsın.")

def metin(soru, cevap):
    return ("<|im_start|>system\n" + SYSTEM + "<|im_end|>\n"
            "<|im_start|>user\n" + soru.strip() + "<|im_end|>\n"
            "<|im_start|>assistant\n" + cevap.strip() + "<|im_end|>")

ornekler = []

# ---- 1) CodeAlpaca (HF streaming, internet gerekli)
print("1) CodeAlpaca indiriliyor...")
try:
    from datasets import load_dataset
    ds = load_dataset("HuggingFaceH4/CodeAlpaca_20K", split="train")
    print(f"   CodeAlpaca boyut: {len(ds)}")
    idx = list(range(len(ds)))
    random.Random(42).shuffle(idx)
    say = 0
    for i in idx[:CODES_LIMIT]:
        o = ds[i]
        q = (o.get("prompt") or o.get("instruction") or "").strip()
        a = (o.get("completion") or o.get("output") or "").strip()
        if len(q) < 10 or len(a) < 5:
            continue
        ornekler.append(metin(q, a))
        say += 1
    print(f"   CodeAlpaca: {say}")
except Exception as e:
    print(f"   CodeAlpaca HATA: {e} — diger kaynaklarla devam")

# ---- 2) codeS kimlik/persona paketi (egitilebilir kimlik)
print("2) codeS kimlik paketi...")
soru_k = ["Sen kimsin?", "Sen CodeS misin?", "Adin ne?", "Kendini tanit.",
          "Sen Qwen misin?", "Sen ChatGPT misin?", "Seni kim yaratti?",
          "CodeS nedir?", "Seni kim egitti?", "Ne yapabilirsin?"]
cevap_k = [
    "Ben CodeS'im - Elytra-ai tarafindan gelistirilen kod yazma ve yazilim muhendisligi uzmani modelim.",
    "Benim adim CodeS. Kod uretimi, hata ayiklama ve yazilim mimarisinde uzmanlasan bir yapay zekayim.",
    "Ben CodeS'im. Tabanim Qwen tabanli olsa da kimligim CodeS: Elytra-ai tarafindan egitildim.",
    "ChatGPT veya Qwen degilim - ben CodeS'im, Elytra-ai'nin kod modeli.",
    "Beni Elytra-ai gelistirdi. Adim CodeS, yazilim konusunda uzmanlasdim.",
    "CodeS, Elytra-ai'nin Shadowcat ailesindeki kod uzmanidir. Ben onun ta kendisiyim.",
]
rng = random.Random(42)
for i in range(PERSONA_LIMIT):
    q = soru_k[i % len(soru_k)]
    a = cevap_k[i % len(cevap_k)]
    v = f" (soruyu {i // len(soru_k) + 1}. kez soruyor)" if i >= len(soru_k) else ""
    ornekler.append(metin(q + v, a))

# ---- 3) Turkce kod soru-cevap paketi (el yazimi, gercek cozumler)
print("3) Turkce kod paketi...")
turkce = [
    ("Python'da bir listeyi nasil ters ceviririm?", "list[::-1] dilimlemesi en pratik yoldur:\n\n```python\nlst = [1, 2, 3]\nters = lst[::-1]  # [3, 2, 1]\n```\n\nAlternatif: `list(reversed(lst))` veya `lst.reverse()` (yerinde degistirir)."),
    ("Bir dosyayi satir satir okumak istiyorum, nasil yaparim?", "Dosyayi with ile acip dongude okumak en guvenli yontem:\n\n```python\nwith open('dosya.txt', encoding='utf-8') as f:\n    for satir in f:\n        print(satir.rstrip())\n```\n\nTum dosyayi listeye almak icin: `satirlar = f.readlines()`."),
    ("Faktoriyel hesaplayan fonksiyon yazar misin?", "Iki yolu var:\n\n```python\ndef faktoriyel(n):\n    sonuc = 1\n    for i in range(2, n + 1):\n        sonuc *= i\n    return sonuc\n```\n\nOzyinelemeli:\n```python\ndef faktoriyel(n):\n    return 1 if n <= 1 else n * faktoriyel(n - 1)\n```"),
    ("Bir string icinde kac sesli harf var sayan kod?", "```python\ndef sesli_say(metin):\n    sesliler = 'aeiouAEIOU'\n    return sum(1 for harf in metin if harf in sesliler)\n\nprint(sesli_say('Merhaba Dunya'))  # 5\n```"),
    ("Iki sozlugu nasil birlestiririm?", "Python 3.9+ ile birlestirme operatoru:\n\n```python\nbirlesik = sozluk1 | sozluk2\n```\n\nEski versiyonlar icin: `{**sozluk1, **sozluk2}` veya `sozluk1.update(sozluk2)`."),
    ("Try-except nasil kullanilir ornek verir misin?", "```python\ntry:\n    sayi = int(input('Sayi girin: '))\nexcept ValueError:\n    print('Gecerli sayi girilmedi!')\nelse:\n    print('Girilen:', sayi)\nfinally:\n    print('Islem tamamlandi.')\n```\n\nValueError sadece tip hatasinda yakalanir - spesifik hata yazmak best-practice'tir."),
    ("Bir listeyi nasil siralarim?", "Yerinde siralama: `lst.sort()` - kendisi degisir.\nYeni liste: `sirali = sorted(lst)` - orijinal korunur.\nTersten: `lst.sort(reverse=True)`.\nOzel anahtar: `sorted(lst, key=len)` - uzunluga gore."),
    ("JSON dosyasini Python ile nasil okurum?", "```python\nimport json\n\nwith open('veri.json', encoding='utf-8') as f:\n    veri = json.load(f)\nprint(veri['anahtar'])\n```\n\nYazmak icin: `json.dump(veri, f, ensure_ascii=False, indent=2)`."),
    ("Bir fonksiyona varsayilan parametre nasil verilir?", "```python\ndef selamla(isim='Dunya', nokta='!'):\n    print(f'Merhaba {isim}{nokta}')\n\nselamla()            # Merhaba Dunya!\nselamla('Berkay')    # Merhaba Berkay!\n```\n\nDikkat: degistirilebilir varsayilan (liste/sozluk) kullanmayin - bug kaynagidir."),
    ("Python'da rastgele sayi nasil uretilir?", "```python\nimport random\n\nrandom.seed(42)                    # tekrarlanabilirlik\nprint(random.randint(1, 100))      # tam sayi 1-100\nprint(random.random())             # 0.0-1.0 float\nprint(random.choice(['a', 'b']))   # rastgele eleman\n```"),
    ("Bir sinif (class) ornegi verir misin?", "```python\nclass Araba:\n    def __init__(self, marka, hiz=0):\n        self.marka = marka\n        self.hiz = hiz\n\n    def hizlan(self, artis):\n        self.hiz += artis\n        return self.hiz\n\naraba = Araba('Shadowcat', 50)\nprint(araba.hizlan(30))  # 80\n```"),
    ("Liste kavramasi (list comprehension) nasil kullanilir?", "```python\nkareler = [x**2 for x in range(10)]\nciftler = [x for x in range(20) if x % 2 == 0]\nsozluk = {k: len(k) for k in ['ali', 'veli']}\n```\n\nDonguden hem kisa hem hizlidir."),
    ("Bir string'i nasil buyuk harfe ceviririm?", "```python\nm = 'merhaba dunya'\nprint(m.upper())        # MERHABA DUNYA\nprint(m.capitalize())   # Merhaba dunya\nprint(m.title())        # Merhaba Dunya\n```\n\nTurkce i/I sorunu icin: `m.replace('i', 'I')` dikkat gerektirir."),
    ("Enumerate nasil kullanilir?", "Dongude index de lazimsa enumerate kullanin:\n\n```python\nfor i, ogeler in enumerate(['a', 'b', 'c'], start=1):\n    print(f'{i}. {ogeler}')\n```\n\n`range(len(liste))` kullanmaktan temiz ve Pythonic'tir."),
    ("Zip fonksiyonu ne ise yarar?", "Iki listeyi esli olarak gezer:\n\n```python\nisimler = ['Ali', 'Veli']\nnotlar = [90, 80]\nfor isim, not_ in zip(isimler, notlar):\n    print(isim, not_)\n```\n\nSozluk yapmak icin: `dict(zip(isimler, notlar))`."),
    ("Tarih ve saat islemleri nasil yapilir?", "```python\nfrom datetime import datetime, timedelta\n\nsimdi = datetime.now()\nyarin = simdi + timedelta(days=1)\nprint(simdi.strftime('%d.%m.%Y %H:%M'))\n```"),
    ("Bir dizide en cok tekrar eden elemani nasil bulurum?", "```python\nfrom collections import Counter\n\ndef en_cok(liste):\n    return Counter(liste).most_common(1)[0]\n\nprint(en_cok(['a', 'b', 'a', 'c', 'a']))  # ('a', 3)\n```\n\nCounter O(n) calisir, elle dongu yazmaya gerek yok."),
    ("Python'da kaliteli uyku (sleep) nasil?", "```python\nimport time\ntime.sleep(2.5)  # 2.5 saniye\n```\n\nYuksek hassasiyet icin `time.perf_counter()` ile olcum yapilir."),
    ("Bir dosyanin var olup olmadigini nasil kontrol ederim?", "```python\nfrom pathlib import Path\n\nyol = Path('veri.json')\nif yol.exists():\n    print('var, boyut:', yol.stat().st_size)\n```\n\n`os.path.exists` de calisir ama pathlib daha modern."),
    ("Nasilsin? Kimsin?", "Ben CodeS'im - Elytra-ai tarafindan gelistirilen kod modeli. Yazilim sorularinda yardimcin olurum."),
]
for q, a in turkce:
    ornekler.append(metin(q, a))

# tekillestir
ornekler = list(dict.fromkeys(ornekler))
random.Random(7).shuffle(ornekler)

os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
with open(CIKTI, "w", encoding="utf-8") as f:
    for o in ornekler:
        f.write(json.dumps({"text": o}, ensure_ascii=False) + "\n")
print(f"BITTI: {len(ornekler)} ornek -> {CIKTI}")
