"""
GulmezCetinerMax - GGUF Donusturme ve Ollama Yukleme
Elytra-ai | Developer: Berkay

Bu script, egitilen modeli GGUF formatina donusturur
ve Ollama'ya yukler.

Kullanim:
    python setup_ollama.py
"""

import os
import subprocess
import sys
from pathlib import Path


def check_ollama() -> bool:
    """Ollama'nin yuklu olup olmadigini kontrol et."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_model_exists(model_name: str) -> bool:
    """Modelin Ollama'da olup olmadigini kontrol et."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return model_name in result.stdout
    except Exception:
        return False


def create_ollama_model():
    """GulmezCetinerMax'i Ollama'ya yukle."""
    print("\n" + "="*60)
    print("GULMEZCETINERMAX - OLLAMA KURULUM")
    print("="*60)

    # Ollama kontrol
    if not check_ollama():
        print("❌ Ollama bulunamadi!")
        print("\nOllama'yi yuklemek icin:")
        print("   1. https://ollama.com/download adresine git")
        print("   2. Windows surumunu indir ve yukle")
        print("   3. 'ollama serve' komutunu calistir")
        return False

    print("✅ Ollama bulundu")

    # Modelfile kontrol
    modelfile_path = Path(__file__).parent / "Modelfile"
    if not modelfile_path.exists():
        print(f"❌ Modelfile bulunamadi: {modelfile_path}")
        return False

    print(f"✅ Modelfile bulundu: {modelfile_path}")

    # Model olustur
    model_name = "gulmzcetinermax:latest"

    if check_model_exists(model_name):
        print(f"⚠️ Model zaten mevcut: {model_name}")
        response = input("Yeniden olusturmak istiyor musunuz? (e/h): ")
        if response.lower() != 'e':
            print("Islem iptal edildi.")
            return False

        # Eski modeli sil
        print(f"Eski model siliniyor...")
        subprocess.run(["ollama", "rm", model_name], capture_output=True)

    print(f"\n🚀 GulmezCetinerMax Ollama'ya yukleniyor...")
    print(f"   Model: {model_name}")
    print(f"   Modelfile: {modelfile_path}")

    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            print(f"\n✅ GulmezCetinerMax basariyla yuklendi!")
            print(f"   Model: {model_name}")

            # Test
            print("\n🧪 Model test ediliyor...")
            test_result = subprocess.run(
                ["ollama", "run", model_name, "Merhaba, kendini kisaca tanit."],
                capture_output=True,
                text=True,
                timeout=120
            )

            if test_result.returncode == 0:
                print("✅ Model test basarili!")
                print(f"\nModel yaniti:\n{test_result.stdout}")
            else:
                print("⚠️ Model test edilemedi ama yuklendi.")

            return True
        else:
            print(f"❌ Model olusturma basarisiz!")
            print(f"Hata: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Islem zaman asimina ugradi (10 dakika)")
        return False


def quick_setup():
    """Hizli kurulum - Ollama'dan base model cek ve Modelfile olustur."""
    print("\n" + "="*60)
    print("GULMEZCETINERMAX - HIZLI KURULUM")
    print("="*60)

    if not check_ollama():
        print("❌ Ollama bulunamadi!")
        print("   https://ollama.com/download")
        return False

    base_model = "qwen2.5-coder:14b"
    print(f"\n📦 Base model kontrol ediliyor: {base_model}")

    if not check_model_exists(base_model):
        print(f"   {base_model} indiriliyor... (bu islem uzun surebilir)")
        result = subprocess.run(
            ["ollama", "pull", base_model],
            capture_output=True,
            text=True,
            timeout=3600
        )
        if result.returncode != 0:
            print(f"❌ Model indirme basarisiz: {result.stderr}")
            return False
        print(f"✅ {base_model} indirildi")
    else:
        print(f"✅ {base_model} zaten mevcut")

    # Ollama'ya yukle
    return create_ollama_model()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GulmezCetinerMax Ollama Kurulum")
    parser.add_argument("--quick", action="store_true", help="Hizli kurulum (base model otomatik indir)")
    parser.add_argument("--test", action="store_true", help="Sadece model test et")
    args = parser.parse_args()

    if args.test:
        model_name = "gulmzcetinermax:latest"
        if check_model_exists(model_name):
            print(f"🧪 {model_name} test ediliyor...")
            result = subprocess.run(
                ["ollama", "run", model_name, "Merhaba, kendini kisaca tanit."],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                print(f"\n{result.stdout}")
            else:
                print(f"❌ Test basarisiz: {result.stderr}")
        else:
            print(f"❌ {model_name} bulunamadi!")
        return

    if args.quick:
        quick_setup()
    else:
        create_ollama_model()


if __name__ == "__main__":
    main()
