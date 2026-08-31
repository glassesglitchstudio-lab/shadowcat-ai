# Model Security — Shadowcat AI

Fine-tuned model agirliklarini AES-256 ile sifreleyip dagitma sistemi.

## Hizli Baslangic

### 1. Bagimliliklari kur
```bash
pip install cryptography
```

### 2. Modelleri sifrele
```bash
# Tek model
python encrypt_model.py -i model.gguf -o model.enc -k "ANAHTARIN"

# Toplu
python encrypt_model.py --batch --input-dir ./models --output-dir ./encrypted -k "ANAHTARIN"

# Streaming (buyuk dosyalar icin - RAM dostu)
python encrypt_model.py -i big_model.gguf -o big.enc -k "ANAHTARIN" --streaming
```

### 3. Sifreli modeli Ollama'ya yukle
```bash
python model_loader.py --enc model.enc -p "ANAHTARIN" -n x_fable_coder
```

### 4. Windows batch
```bash
# Sifrele
encrypt_my_models.bat

# Yukle
load_my_models.bat
```

---

## SIFRE NEREDEN ALINIR?

### Adim 1: Discord sunucusuna katil
https://discord.gg/glassesglitchstudio

### Adim 2: #model-guvenlik kanalina git
Sunucuda `#model-guvenlik` veya `#sifreli-modeller` kanalinda sifre paylasilir.

### Adim 3: Sifreyi kopyala
Discord'da paylasilan sifreyi kopyala.

### Adim 4: load_my_models.bat calistir
Bat dosyasini calistirdiginda senden sifre isteyecek. Discord'dan aldigin sifreyi yapistir.

### Adim 5: Modeli calistir
```bash
ollama run x_fable_coder:secure
ollama run glitch_opus:secure
```

---

## DAGITIM AKISI

```
1. Model sifrele (encrypt_my_models.bat)
   -> encrypted_models/x_fable_coder.enc (8.5 GB)
   -> encrypted_models/glitch_opus.enc (6.2 GB)

2. GitHub Releases'a yukle
   -> gh release create secure-v1.0 encrypted_models/*.enc

3. Discord'da sifreyi paylas
   -> #model-guvenlik kanalinda

4. Kullanici indirir
   -> .enc dosyasini indirir
   -> load_my_models.bat calistirir
   -> Discord'dan sifreyi girer
   -> ollama run x_fable_coder:secure
```

## DOSYA YAPISI

```
model_security/
├── encrypt_model.py           # Sifreleme araci (streaming destekli)
├── model_loader.py            # Cozme + Ollama'ya yukleme
├── encrypted_model_provider.py # Core entegrasyonu
├── encrypt_my_models.bat      # Windows sifreleme scripti
├── load_my_models.bat         # Windows yukleme scripti
├── encrypted_models/          # Sifreli dosyalar (.enc)
└── README.md                  # Bu dosya
```

## GUVENLIK

- **AES-256-CTR** (streaming) / **AES-256-CBC** (klasik)
- **PBKDF2-SHA256** (100K iterasyon)
- Salt ve nonce rastgele uretiliyor
- Model dosyasi disk'te asla cozulmez (sadece streaming ile RAM'de islenir)
- Anahtar kullanicilara ozel, Discord'dan paylasilir
- 100MB+ dosyalar icin otomatik streaming modu (RAM dostu)

## STREAMING MODU

Buyuk model dosyalari (8+ GB) icin ozel streaming modu:
- Dosya 1MB'lik parcalara bolunur
- Her parca ayri ayri sifrelenir/cozulur
- RAM'de sadece 1MB bulundurulur
- PC kasilmaz, yavaslamaz

```bash
# Zorla streaming
python encrypt_model.py -i big.enc --streaming

# Zorla CBC (kucuk dosyalar icin)
python encrypt_model.py -i small.enc --no-streaming
```

## KULLANIM ORNEKLERI

```bash
# Sifrele
python encrypt_model.py -i model.gguf -o model.enc -k "sifrem"

# Sifre coz ve Ollama'ya yukle
python model_loader.py --enc model.enc -p "sifrem" -n my_model

# Metadata goster
python model_loader.py --enc model.enc -p "sifrem" --info

# Sifre dogrula
python model_loader.py --enc model.enc -p "sifrem" --verify
```
