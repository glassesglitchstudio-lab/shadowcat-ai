"""
Sifreli Model Saglayici — shadowcat_core.py entegrasyonu
Sifreli modelleri bellekte cozup Ollama'ya yukler.
Streaming destegi: buyuk dosyalar icin RAM dostu.
"""

import os
import gc
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, List

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

CHUNK_SIZE = 1024 * 1024  # 1MB


class EncryptedModelProvider:
    """Sifreli model dosyalarini yonet sinifi."""

    def __init__(self, encrypted_dir: str = None, password: str = None):
        if encrypted_dir is None:
            encrypted_dir = os.path.join(os.path.dirname(__file__), "encrypted_models")
        self.encrypted_dir = Path(encrypted_dir)
        self.password = password
        self._loaded_models: Dict[str, bool] = {}
        self.encrypted_dir.mkdir(parents=True, exist_ok=True)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        import hashlib
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000, 32)

    def decrypt_to_memory(self, enc_path: str) -> tuple:
        """Sifreli dosyayi bellege coz."""
        if not HAS_CRYPTO:
            raise RuntimeError("cryptography yuklu degil: pip install cryptography")

        with open(enc_path, 'rb') as f:
            metadata_len = int.from_bytes(f.read(4), 'big')
            metadata = json.loads(f.read(metadata_len).decode('utf-8'))
            ciphertext = f.read()

        salt = bytes.fromhex(metadata['salt'])
        key = self._derive_key(self.password, salt)
        algorithm = metadata.get('algorithm', 'AES-256-CBC')

        if algorithm == 'AES-256-CTR':
            nonce = bytes.fromhex(metadata['nonce'])
            initial_counter = bytes.fromhex(metadata['initial_counter'])
            counter_block = bytearray(nonce + initial_counter)

            cipher = Cipher(algorithms.AES(key), modes.CTR(bytes(counter_block)), backend=default_backend())
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        else:
            iv = bytes.fromhex(metadata['iv'])
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()

            unpadder = sym_padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded) + unpadder.finalize()

        return plaintext, metadata

    def decrypt_streaming(self, enc_path: str, output_path: str) -> bool:
        """Sifreli dosyayi streaming ile disk'e coz (RAM dostu)."""
        if not HAS_CRYPTO:
            raise RuntimeError("cryptography yuklu degil")

        with open(enc_path, 'rb') as f:
            metadata_len = int.from_bytes(f.read(4), 'big')
            metadata = json.loads(f.read(metadata_len).decode('utf-8'))

        salt = bytes.fromhex(metadata['salt'])
        key = self._derive_key(self.password, salt)
        algorithm = metadata.get('algorithm', 'AES-256-CBC')
        original_size = metadata['original_size']

        if algorithm == 'AES-256-CTR':
            nonce = bytes.fromhex(metadata['nonce'])
            initial_counter = bytes.fromhex(metadata['initial_counter'])
            counter_block = bytearray(nonce + initial_counter)

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(enc_path, 'rb') as fin, open(output_path, 'wb') as fout:
                fin.read(4 + metadata_len)

                cipher = Cipher(algorithms.AES(key), modes.CTR(bytes(counter_block)), backend=default_backend())
                decryptor = cipher.decryptor()

                enc_size = metadata.get('encrypted_size', original_size)
                bytes_read = 0

                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    decrypted = decryptor.update(chunk)
                    fout.write(decrypted)
                    bytes_read += len(chunk)

                fout.write(decryptor.finalize())

            actual = output_path.stat().st_size
            assert actual == original_size, f"Boyut uyumsuzlugu: {actual} != {original_size}"
            return True
        else:
            model_data, _ = self.decrypt_to_memory(enc_path)
            with open(output_path, 'wb') as f:
                f.write(model_data)
            del model_data  # RAM'i serbest birak
            gc.collect()
            return True

    def load_model(self, model_name: str, tag: str = "secure") -> bool:
        """Sifreli modeli Ollama'ya yukle."""
        if model_name in self._loaded_models:
            return True

        enc_file = self.encrypted_dir / f"{model_name}.enc"
        if not enc_file.exists():
            print(f"HATA: {model_name}.enc bulunamadi: {enc_file}")
            return False

        if not self.password:
            print("HATA: Sifre ayarlanmamis")
            return False

        # Metadata oku - algorithm bilgisi icin
        with open(enc_file, 'rb') as f:
            metadata_len = int.from_bytes(f.read(4), 'big')
            metadata = json.loads(f.read(metadata_len).decode('utf-8'))

        algorithm = metadata.get('algorithm', 'AES-256-CBC')
        file_size = enc_file.stat().st_size

        # Streaming modu: CTR veya 100MB+
        use_streaming = algorithm == 'AES-256-CTR' or file_size > 100 * 1024 * 1024

        print(f"  {model_name} cozuluyor ({algorithm})...")

        with tempfile.TemporaryDirectory(prefix="glasses_") as tmpdir:
            gguf_path = os.path.join(tmpdir, metadata['original_name'])

            if use_streaming:
                self.decrypt_streaming(str(enc_file), gguf_path)
            else:
                model_data, _ = self.decrypt_to_memory(str(enc_file))
                with open(gguf_path, 'wb') as f:
                    f.write(model_data)
                del model_data  # RAM'i serbest birak
                gc.collect()

            modelfile_path = os.path.join(tmpdir, 'Modelfile')
            with open(modelfile_path, 'w') as f:
                f.write(f'FROM {gguf_path}\n')

            full_name = f"{model_name}:{tag}"
            print(f"  Ollama'ya yukleniyor: {full_name}")
            result = subprocess.run(
                ['ollama', 'create', full_name, '-f', modelfile_path],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                self._loaded_models[model_name] = True
                print(f"  {model_name} yuklendi ({full_name})")
                return True
            else:
                print(f"  {model_name} yukleme hatasi: {result.stderr}")
                return False

    def get_model_endpoint(self, model_name: str) -> str:
        tag = "secure" if model_name in self._loaded_models else "latest"
        return f"ollama/{model_name}:{tag}"

    def list_encrypted(self) -> List[str]:
        if not self.encrypted_dir.exists():
            return []
        return [f.stem for f in self.encrypted_dir.glob("*.enc")]

    def set_password(self, password: str):
        self.password = password

    def has_encrypted_models(self) -> bool:
        return len(self.list_encrypted()) > 0


# Singleton
_provider = None

def get_encrypted_provider(password: str = None) -> EncryptedModelProvider:
    global _provider
    if _provider is None:
        _provider = EncryptedModelProvider(password=password)
    elif password:
        _provider.set_password(password)
    return _provider
