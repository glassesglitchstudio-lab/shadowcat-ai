# Opti-LoRA: Hızlı Kurulum Rehberi (Minimal Disk)
# 2-3 GB toplam disk kullanımı
# C:\Users\ErCuM\CascadeProjects\shadowcat\opti-lora\

# === ADIM 1: Python venv (küçük, 500 MB) ===
cd C:\Users\ErCuM\CascadeProjects\shadowcat\opti-lora
python -m venv venv
# Aktif et: venv\Scripts\activate

# === ADIM 2: Minimal pip install (~2-3 GB) ===
# PyTorch (CPU only — Kaggle'da GPU, lokalde CPU yeterli test için)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Gerekli paketler
pip install transformers==4.40.0
pip install peft==0.10.0
pip install bitsandbytes==0.43.0
pip install accelerate==0.29.0
pip install datasets
pip install trl  # SFTTrainer
pip install sentencepiece  # Türkçe tokenizer için

# NOT: Flash Attention 2 atlanıyor (Windows'ta zor derlenir, Kaggle'da lazım)
# NOT: Unsloth atlanıyor (sadece Linux, Kaggle'da lazım)
