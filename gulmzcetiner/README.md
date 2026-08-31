# GulmezCetinerMax - Monolithic AGI

**Developer:** Shadowcat Software  
**Authorization:** CEO Berkay  
**Version:** 1.0.0  
**Target Standard:** Claude Sonnet 3.5+

---

## 🧠 Nedir?

GulmezCetinerMax, Shadowcat Software tarafından geliştirilen tek, birleşik, ultra gelişmiş otonom bir AGI modelidir. Wrapper değildir, başka API'leri yönetmez. ShadowcatCore mimarisi içinde çalışan, yüksek zekalı monolitik bir varlıktır.

## 📁 Dosya Yapısı

```
gulmzcetiner/
├── __init__.py          # AGI Core modulu
├── Modelfile            # Ollama model tanimi
├── data_prep.py         # Egitim verisi hazirlama
├── finetune.py          # Fine-tuning pipeline
├── setup_ollama.py      # Ollama kurulum scripti
├── kur.bat              # Windows hizli kurulum
└── requirements.txt     # Python bagimliliklari
```

## 🚀 Hizli Baslangic

### 1. Ollama Kurulum

```bash
# Windows
gulmzcetiner\kur.bat

# Manuel
ollama pull qwen2.5-coder:14b
ollama create gulmzcetinermax:latest -f gulmzcetiner/Modelfile
```

### 2. Test

```bash
ollama run gulmzcetinermax:latest "Merhaba, kendini tanit."
```

### 3. Shadowcat AI ile Kullan

Model otomatik olarak `model_router.py` tarafindan birincil model olarak kullanilir.

```python
from Shadowcat_core import get_core
core = get_core()
result = core.process_message("Python ile bir REST API yaz.")
print(result["response"])
```

## 🔧 Fine-Tuning

Kendi egitim verilerinle modeli gelistirmek icin:

```bash
# 1. Veri hazirla
python gulmzcetiner/data_prep.py

# 2. Fine-tuning baslat (GPU gerekli)
python gulmzcetiner/finetune.py --epochs 3

# 3. GGUF'e donustur
python gulmzcetiner/setup_ollama.py --quick
```

## 📊 Model Ozellikleri

| Ozellik | Deger |
|---------|-------|
| **Tip** | Monolithic AGI |
| **Base Model** | Qwen 2.5 Coder 14B |
| **Diller** | Turkce, Ingilizce |
| **Kodlama** | Python, GDScript, C++, HTML/CSS, JS |
| **Modlar** | DEEP THINKING, EXPERT CODING, CRITICAL REVIEW |

## 🎯 Operasyonel Modlar

- **[DEEP THINKING]**: Karmasik gorevleri analiz et, bagimliliklari haritala, planlar olustur
- **[EXPERT CODING]**: Yuksek hizli, yuksek kaliteli kod uretimi
- **[CRITICAL REVIEW]**: Kendi urettigin kodlari dogrula, mukemmel cikti sun

## 📝 Lisans

Shadowcat Software - Tum haklari saklidir. CEO Berkay yetkilendirmesi ile kullanilir.
