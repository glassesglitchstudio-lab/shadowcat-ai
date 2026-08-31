"""
Shadowcat - RAG (Retrieval-Augmented Generation) Sistemi
Shadowcat AI için tamamen yerel/offline çalışan RAG motoru

Özellikler:
- PDF, TXT, MD, HTML, CSV dosyalarından metin çıkarma
- Akıllı metin bölümleme (chunking) ve örtüşme (overlap)
- sentence-transformers ile yerel embedding (offline)
- Ollama embedding desteği (online/yerel) 
- FAISS / JSON tabanlı vektör depolama
- Anlamsal arama (semantic search) ile bağlam bulma
- Web sayfası tarama ve indeksleme
- Konuşma bağlamını RAG ile zenginleştirme
- Bilgi tabanı yönetimi (ekle, sil, listele, güncelle)
"""

import csv
import hashlib
import io
import json
import logging
import os
import re
import time
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

# ──────────────────────────────────────────────────────────────────
# Logging Yapılandırması
# ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("Shadowcat.RAG")
logger.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_fmt = logging.Formatter(
    "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_ch.setFormatter(_fmt)
if not logger.handlers:
    logger.addHandler(_ch)


# ──────────────────────────────────────────────────────────────────
# İsteğe Bağlı Bağımlılıklar (graceful fallback)
# ──────────────────────────────────────────────────────────────────

_has_sentence_transformers = False
_has_faiss = False
_has_pypdf2 = False
_has_pdfplumber = False
_has_pdfminer = False
_has_beautifulsoup = False

try:
    import sentence_transformers  # noqa: F401

    _has_sentence_transformers = True
except ImportError:
    pass

try:
    import faiss  # noqa: F401

    _has_faiss = True
except ImportError:
    pass

try:
    import PyPDF2  # noqa: F401

    _has_pypdf2 = True
except ImportError:
    try:
        import pdfplumber  # noqa: F401

        _has_pdfplumber = True
    except ImportError:
        try:
            import pdfminer  # noqa: F401

            _has_pdfminer = True
        except ImportError:
            pass

try:
    from bs4 import BeautifulSoup  # noqa: F401

    _has_beautifulsoup = True
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────
# Sabitler
# ──────────────────────────────────────────────────────────────────

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
DEFAULT_TOP_K = 5
DEFAULT_MAX_CONTEXT_CHUNKS = 10
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_RAG_DIR = "rag_storage"

SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".txt", ".md", ".html", ".htm", ".csv"}

# Embedding boyutları (kullanılan modele göre)
KNOWN_EMBEDDING_DIMS: Dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "intfloat/multilingual-e5-small": 384,
    "intfloat/multilingual-e5-base": 768,
    "nomic-embed-text": 768,
    "llama3.1:latest": 4096,
}


# ═══════════════════════════════════════════════════════════════════
# RAGConfig - Yapılandırma Sınıfı
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RAGConfig:
    """
    RAG sistemi yapılandırması.

    Tüm RAG bileşenlerinin davranışını kontrol eden parametreleri içerir.
    Varsayılan değerler küçük/orta ölçekli projeler için optimize edilmiştir.

    Attributes:
        embedding_model: sentence-transformers model adı
        chunk_size: Metin bölümleme boyutu (karakter cinsinden)
        chunk_overlap: Bölümler arası örtüşme miktarı
        top_k: Arama sonuçlarında döndürülecek en iyi eşleşme sayısı
        max_context_chunks: Prompt'a eklenecek maksimum chunk sayısı
        max_context_tokens: LLM bağlamı için maksimum token sayısı (0 = sınırsız)
        use_faiss: FAISS kullanılsın mı (True) yoksa JSON depolama mı
        use_ollama_embeddings: sentence-transformers yerine Ollama kullanılsın mı
        ollama_base_url: Ollama API adresi
        ollama_embedding_model: Ollama embedding model adı (örn. "nomic-embed-text")
        storage_path: Vektör ve belge deposu dizini
        device: sentence-transformers cihazı ("cpu", "cuda", "auto")
        batch_size: Embedding oluşturma batch boyutu
        enable_cache: Embedding önbellekleme açık mı
    """

    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    top_k: int = DEFAULT_TOP_K
    max_context_chunks: int = DEFAULT_MAX_CONTEXT_CHUNKS
    max_context_tokens: int = 0
    use_faiss: bool = True
    use_ollama_embeddings: bool = False
    ollama_base_url: str = DEFAULT_OLLAMA_URL
    ollama_embedding_model: str = "nomic-embed-text"
    storage_path: Union[str, Path] = DEFAULT_RAG_DIR
    device: str = "cpu"
    batch_size: int = 32
    enable_cache: bool = True

    def __post_init__(self):
        """Varsayılan değerleri normalize et ve doğrula."""
        self.storage_path = Path(self.storage_path)

        if self.chunk_overlap >= self.chunk_size:
            logger.warning(
                "chunk_overlap (%d) >= chunk_size (%d), overlap %%50'ye düşürüldü.",
                self.chunk_overlap,
                self.chunk_size,
            )
            self.chunk_overlap = max(1, self.chunk_size // 2)

        if self.device == "auto":
            try:
                import torch

                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"

    @property
    def embedding_dim(self) -> int:
        """Modelin embedding boyutunu döndürür."""
        model_key = (
            self.ollama_embedding_model
            if self.use_ollama_embeddings
            else self.embedding_model
        )
        return KNOWN_EMBEDDING_DIMS.get(model_key, 384)

    def to_dict(self) -> Dict[str, Any]:
        """Yapılandırmayı sözlük olarak döndürür."""
        d = {k: str(v) if isinstance(v, Path) else v for k, v in self.__dict__.items()}
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGConfig":
        """Sözlükten RAGConfig örneği oluşturur."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════
# DocumentIndexer - Belge İşleme ve Bölümleme
# ═══════════════════════════════════════════════════════════════════

class DocumentIndexer:
    """
    Belge işleme ve metin bölümleme (chunking) motoru.

    Farklı dosya türlerinden (PDF, TXT, MD, HTML, CSV) metin çıkarır,
    temizler ve RAG için uygun boyutlu parçalara böler.

    Kullanım:
        indexer = DocumentIndexer(chunk_size=512, chunk_overlap=64)
        chunks = indexer.process_file("belge.pdf")
        chunks = indexer.process_text("Uzun metin...")
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        if chunk_overlap >= chunk_size:
            chunk_overlap = max(1, chunk_size // 2)

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._stats: Dict[str, Any] = {"total_documents": 0, "total_chunks": 0}

    # ── Metin Çıkarma ──────────────────────────────────────────

    def extract_text(self, file_path: Union[str, Path]) -> Tuple[str, str]:
        """
        Bir dosyadan ham metin çıkarır.

        Args:
            file_path: İşlenecek dosyanın yolu.

        Returns:
            (çıkarılan_metin, dosya_türü) ikilisi.

        Raises:
            FileNotFoundError: Dosya mevcut değilse.
            ValueError: Desteklenmeyen dosya türü veya okuma hatası.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Desteklenmeyen dosya türü: '{ext}'. "
                f"Desteklenen: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        extractors = {
            ".txt": self._extract_txt,
            ".md": self._extract_txt,
            ".html": self._extract_html,
            ".htm": self._extract_html,
            ".pdf": self._extract_pdf,
            ".csv": self._extract_csv,
        }

        extractor = extractors.get(ext)
        if extractor is None:
            raise ValueError(f"{ext} için çıkarıcı bulunamadı.")

        text = extractor(path)
        file_type = ext.lstrip(".")
        return text, file_type

    def _extract_txt(self, path: Path) -> str:
        """Düz metin ve Markdown dosyalarından metin çıkarır."""
        encodings = ["utf-8", "utf-16", "windows-1254", "iso-8859-9", "latin-1"]
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _extract_html(self, path: Path) -> str:
        """HTML dosyasından metin çıkarır (BeautifulSoup ile)."""
        raw = self._extract_txt(path)
        if _has_beautifulsoup:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(raw, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text
        else:
            headless = re.sub(r"<[^>]+>", " ", raw)
            headless = re.sub(r"\s+", " ", headless).strip()
            return headless

    def _extract_pdf(self, path: Path) -> str:
        """PDF dosyasından metin çıkarır (çoklu backend desteği)."""
        if _has_pypdf2:
            try:
                return self._extract_pdf_pypdf2(path)
            except Exception as e:
                logger.warning("PyPDF2 başarısız, alternatif deneniyor: %s", e)
        if _has_pdfplumber:
            try:
                return self._extract_pdf_pdfplumber(path)
            except Exception as e:
                logger.warning("pdfplumber başarısız, alternatif deneniyor: %s", e)
        if _has_pdfminer:
            try:
                return self._extract_pdf_pdfminer(path)
            except Exception as e:
                logger.warning("pdfminer başarısız: %s", e)
        raise RuntimeError(
            "PDF çıkarma için bir kütüphane gerekli. "
            "Kurulum: pip install PyPDF2 veya pdfplumber veya pdfminer.six"
        )

    def _extract_pdf_pypdf2(self, path: Path) -> str:
        """PyPDF2 ile PDF metni çıkarır."""
        import PyPDF2

        pages = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)

    def _extract_pdf_pdfplumber(self, path: Path) -> str:
        """pdfplumber ile PDF metni çıkarır."""
        import pdfplumber

        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)

    def _extract_pdf_pdfminer(self, path: Path) -> str:
        """pdfminer ile PDF metni çıkarır."""
        from pdfminer.high_level import extract_text as pdfminer_extract

        return pdfminer_extract(str(path))

    def _extract_csv(self, path: Path) -> str:
        """CSV dosyasından metin çıkarır (insan tarafından okunabilir formatta)."""
        lines = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                lines.append("Sütunlar: " + ", ".join(header))
            for row in reader:
                line = " | ".join(
                    cell.strip() for cell in row if cell and cell.strip()
                )
                if line:
                    lines.append(line)
        return "\n".join(lines) if lines else ""

    # ── Metin Bölümleme (Chunking) ─────────────────────────────

    def chunk_text(self, text: str, source: str = "") -> List[Dict[str, Any]]:
        """
        Metni akıllı şekilde bölümlere ayırır.

        Strateji (recursive):
            1. Önce paragraflara böl (\\n\\n)
            2. Büyük paragrafları cümlelere böl
            3. Hala büyükse karakter bazında böl
            4. Bölümler arasına overlap ekle

        Args:
            text: Bölünecek ham metin.
            source: Kaynak dosya adı (metadata için).

        Returns:
            Her biri {"text": ..., "metadata": {...}} şeklinde chunk listesi.
        """
        chunks: List[Dict[str, Any]] = []
        if not text or not text.strip():
            return chunks

        source_name = Path(source).name if source else "bilinmeyen"
        doc_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        # Adım 1: Paragraflara böl
        paragraphs = re.split(r"\n\s*\n", text.strip())
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        buffer = ""
        for para in paragraphs:
            if len(buffer) + len(para) + 1 <= self.chunk_size or not buffer:
                buffer = (buffer + "\n\n" + para).strip() if buffer else para
            else:
                if buffer:
                    chunks.extend(
                        self._split_large_chunk(buffer, source_name, doc_id)
                    )
                buffer = para

        if buffer:
            chunks.extend(self._split_large_chunk(buffer, source_name, doc_id))

        # Overlap ekle (bitişik chunk'lar arasına)
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        # Metadata ekle
        now = datetime.now().isoformat()
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i
            chunk["metadata"]["total_chunks"] = len(chunks)
            chunk["metadata"]["timestamp"] = now

        self._stats["total_documents"] += 1
        self._stats["total_chunks"] += len(chunks)

        return chunks

    def _split_large_chunk(
        self, text: str, source: str, doc_id: str
    ) -> List[Dict[str, Any]]:
        """Büyük bir metin parçasını recursive olarak böler."""
        if len(text) <= self.chunk_size:
            return [
                {
                    "text": text,
                    "metadata": {
                        "source": source,
                        "doc_id": doc_id,
                    },
                }
            ]

        chunks = []
        # Önce cümle bazında böl
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current = ""

        for sent in sentences:
            if len(current) + len(sent) + 1 <= self.chunk_size:
                current = (current + " " + sent).strip() if current else sent
            else:
                if current:
                    chunks.append(
                        {
                            "text": current,
                            "metadata": {"source": source, "doc_id": doc_id},
                        }
                    )
                # Eğer tek bir cümle chunk_size'dan büyükse, kelime bazında böl
                if len(sent) > self.chunk_size:
                    words = sent.split()
                    current = ""
                    for word in words:
                        if len(current) + len(word) + 1 <= self.chunk_size:
                            current = (current + " " + word).strip() if current else word
                        else:
                            if current:
                                chunks.append(
                                    {
                                        "text": current,
                                        "metadata": {
                                            "source": source,
                                            "doc_id": doc_id,
                                        },
                                    }
                                )
                            current = word
                    if current:
                        chunks.append(
                            {
                                "text": current,
                                "metadata": {
                                    "source": source,
                                    "doc_id": doc_id,
                                },
                            }
                        )
                    current = ""
                else:
                    current = sent

        if current:
            chunks.append(
                {
                    "text": current,
                    "metadata": {"source": source, "doc_id": doc_id},
                }
            )

        return chunks

    def _apply_overlap(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bitişik chunk'lar arasına overlap metni ekler."""
        overlapped = []
        last_sentences: List[str] = []

        for i, chunk in enumerate(chunks):
            text = chunk["text"]
            sentences = re.split(r"(?<=[.!?])\s+", text)

            if last_sentences and self.chunk_overlap > 0:
                overlap_text = " ".join(last_sentences)
                if len(overlap_text) > self.chunk_overlap:
                    overlap_text = overlap_text[-self.chunk_overlap :]
                    overlap_text = overlap_text[overlap_text.find(" ") + 1 :]
                text = overlap_text + " " + text if overlap_text else text

            # Son chunk'ın son cümlelerini overlap için sakla
            last_sentences = []
            char_count = 0
            for sent in reversed(sentences):
                if char_count + len(sent) <= self.chunk_size // 4:
                    last_sentences.insert(0, sent)
                    char_count += len(sent)
                else:
                    break

            overlapped.append(
                {
                    "text": text.strip(),
                    "metadata": dict(chunk["metadata"]),
                }
            )

        return overlapped

    # ── Dışa Dönük API ─────────────────────────────────────────

    def process_file(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Bir dosyayı işler ve chunk'lara ayırır.

        Args:
            file_path: İşlenecek dosyanın yolu.

        Returns:
            Chunk listesi (her biri {"text": ..., "metadata": {...}}).
        """
        text, file_type = self.extract_text(file_path)
        chunks = self.chunk_text(text, source=str(file_path))
        for chunk in chunks:
            chunk["metadata"]["file_type"] = file_type
        logger.info(
            "Dosya işlendi: %s -> %d chunk (%s)", file_path, len(chunks), file_type
        )
        return chunks

    def process_text(
        self, text: str, source: str = "inline_text"
    ) -> List[Dict[str, Any]]:
        """
        Ham metni işler ve chunk'lara ayırır.

        Args:
            text: İşlenecek metin.
            source: Kaynak tanımlayıcı (metadata için).

        Returns:
            Chunk listesi.
        """
        return self.chunk_text(text, source=source)

    def get_stats(self) -> Dict[str, Any]:
        """İşlem istatistiklerini döndürür."""
        return dict(self._stats)

    def reset_stats(self):
        """İstatistikleri sıfırlar."""
        self._stats = {"total_documents": 0, "total_chunks": 0}


# ═══════════════════════════════════════════════════════════════════
# EmbeddingModel - Metin Vektörleştirme
# ═══════════════════════════════════════════════════════════════════

class EmbeddingModel:
    """
    Metin embedding (vektör) oluşturma motoru.

    sentence-transformers ile tamamen yerel (offline) çalışır.
    Ollama tabanlı embedding de alternatif olarak desteklenir.

    Kullanım:
        emb = EmbeddingModel(config)
        vectors = emb.encode(["metin 1", "metin 2"])
    """

    def __init__(self, config: RAGConfig):
        self.config = config
        self._model = None
        self._model_lock = Lock()
        self._cache: Dict[str, np.ndarray] = {}
        self._fallback_active = False

    def _load_sentence_transformer(self):
        """sentence-transformers modelini yükler."""
        if _has_sentence_transformers:
            try:
                import sentence_transformers as st

                logger.info(
                    "sentence-transformers yükleniyor: %s (%s)",
                    self.config.embedding_model,
                    self.config.device,
                )
                self._model = st.SentenceTransformer(
                    self.config.embedding_model, device=self.config.device
                )
                self._fallback_active = False
                logger.info("Embedding model hazır: %s", self.config.embedding_model)
            except Exception as e:
                logger.error(
                    "sentence-transformers yüklenemedi (%s). Ollama deneniyor.",
                    e,
                )
                raise
        else:
            raise ImportError("sentence-transformers paketi kurulu değil.")

    def _get_ollama_embedding(self, text: str) -> Optional[np.ndarray]:
        """Ollama API ile tek bir metin için embedding alır."""
        import requests

        payload = {
            "model": self.config.ollama_embedding_model,
            "prompt": text,
        }
        try:
            resp = requests.post(
                f"{self.config.ollama_base_url}/api/embeddings",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if emb:
                return np.array(emb, dtype=np.float32)
        except requests.exceptions.RequestException as e:
            logger.debug("Ollama embedding hatası: %s", e)
        return None

    def _get_ollama_embeddings_batch(self, texts: List[str]) -> Optional[np.ndarray]:
        """Ollama ile batch embedding (her metin için ayrı istek)."""
        all_embs = []
        for t in texts:
            emb = self._get_ollama_embedding(t)
            if emb is not None:
                all_embs.append(emb)
            else:
                all_embs.append(np.zeros(self.config.embedding_dim, dtype=np.float32))
        return np.array(all_embs, dtype=np.float32) if all_embs else None

    def _get_ollama_embeddings_multi(self, texts: List[str]) -> Optional[np.ndarray]:
        """Ollama'nın batch embedding API'sini dener."""
        import requests

        payload = {
            "model": self.config.ollama_embedding_model,
            "prompts": texts,
        }
        try:
            resp = requests.post(
                f"{self.config.ollama_base_url}/api/embeddings",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return np.array(embeddings, dtype=np.float32)
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            return self._get_ollama_embeddings_batch(texts)
        return None

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Metin listesini vektörlere dönüştürür.

        Args:
            texts: Vektörleştirilecek metin listesi.

        Returns:
            shape=(len(texts), embedding_dim) numpy array.
        """
        if not texts:
            return np.empty((0, self.config.embedding_dim), dtype=np.float32)

        filtered = [t for t in texts if t and t.strip()]
        if not filtered:
            return np.zeros((len(texts), self.config.embedding_dim), dtype=np.float32)

        results: List[Optional[np.ndarray]] = []

        if self.config.enable_cache:
            uncached = []
            idx_map = []
            for i, t in enumerate(texts):
                key = hashlib.md5(t.encode("utf-8")).hexdigest()
                cached = self._cache.get(key)
                if cached is not None:
                    results.append((i, cached))
                else:
                    uncached.append(t)
                    idx_map.append((i, key))
            if uncached:
                vectors = self._encode_batch(uncached)
                for (orig_idx, cache_key), vec in zip(idx_map, vectors):
                    self._cache[cache_key] = vec
                    results.append((orig_idx, vec))
            results.sort(key=lambda x: x[0])
            return np.array([r[1] for r in results], dtype=np.float32)

        return self._encode_batch(texts)

    def _encode_batch(self, texts: List[str]) -> np.ndarray:
        """Batch halinde embedding oluşturur."""
        if self.config.use_ollama_embeddings:
            emb = self._get_ollama_embeddings_multi(texts)
            if emb is not None:
                return emb
            logger.warning("Ollama embedding başarısız, sentence-transformers deneniyor.")

        try:
            with self._model_lock:
                if self._model is None:
                    self._load_sentence_transformer()
                vectors = self._model.encode(
                    texts,
                    batch_size=self.config.batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
            return np.array(vectors, dtype=np.float32)
        except Exception as e:
            if not self._fallback_active and not self.config.use_ollama_embeddings:
                logger.warning(
                    "sentence-transformers hatası (%s). Ollama fallback deneniyor.", e
                )
                self._fallback_active = True
                emb = self._get_ollama_embeddings_multi(texts)
                if emb is not None:
                    return emb
            raise RuntimeError(f"Embedding oluşturulamadı: {e}")

    def encode_single(self, text: str) -> np.ndarray:
        """Tek bir metni vektörleştirir."""
        return self.encode([text])[0]

    def get_dimension(self) -> int:
        """Embedding boyutunu döndürür."""
        test_vec = self.encode(["test"])
        return test_vec.shape[1]

    def clear_cache(self):
        """Embedding önbelleğini temizler."""
        self._cache.clear()
        logger.debug("Embedding cache temizlendi.")

    def unload_model(self):
        """Modeli bellekten boşaltır."""
        with self._model_lock:
            self._model = None
        self.clear_cache()
        logger.info("Embedding modeli bellekten boşaltıldı.")


# ═══════════════════════════════════════════════════════════════════
# VectorStore - Vektör Depolama ve Arama
# ═══════════════════════════════════════════════════════════════════

class VectorStore:
    """
    Embedding vektörlerini depolar ve anlamsal arama yapar.

    FAISS (Facebook AI Similarity Search) birincil depolama,
    JSON + NumPy ikincil (fallback) depolama olarak kullanılır.

    Kullanım:
        store = VectorStore(config, embedding_model)
        store.add_chunks(chunks)
        results = store.search("soru metni", top_k=5)
    """

    def __init__(self, config: RAGConfig, embedding_model: EmbeddingModel):
        self.config = config
        self.embedder = embedding_model
        self._lock = Lock()

        # Veri yapıları
        self._chunks: List[Dict[str, Any]] = []
        self._index = None
        self._dimension: int = config.embedding_dim
        self._is_faiss = False

        self._storage_dir = config.storage_path / "vectors"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._storage_dir / "index.faiss"
        self._chunks_path = self._storage_dir / "chunks.json"
        self._meta_path = self._storage_dir / "index_meta.json"

        self._setup_index()

    def _setup_index(self):
        """Vektör indeksini başlatır (FAISS veya numpy)."""
        if self.config.use_faiss and _has_faiss:
            try:
                import faiss as faiss_lib

                self._dimension = self.embedder.get_dimension()
                self._index = faiss_lib.IndexFlatIP(self._dimension)
                self._is_faiss = True
                logger.info("FAISS indeks oluşturuldu (dim=%d)", self._dimension)

                if self._index_path.exists():
                    try:
                        self._index = faiss_lib.read_index(str(self._index_path))
                        logger.info("FAISS indeks diskten yüklendi.")
                        if self._chunks_path.exists():
                            with open(self._chunks_path, "r", encoding="utf-8") as f:
                                self._chunks = json.load(f)
                    except Exception as e:
                        logger.warning("FAISS indeks yüklenemedi, yeniden oluşturuluyor: %s", e)
                        self._index = faiss_lib.IndexFlatIP(self._dimension)
                        self._chunks = []
                return
            except Exception as e:
                logger.warning("FAISS başlatılamadı, JSON depolama kullanılacak: %s", e)

        self._is_faiss = False
        self._chunks = []
        self._load_json_index()
        logger.info("JSON tabanlı vektör depolama kullanılıyor (dim=%d)", self._dimension)

    def _load_json_index(self):
        """JSON + .npy depolamayı yükler."""
        if self._chunks_path.exists():
            try:
                with open(self._chunks_path, "r", encoding="utf-8") as f:
                    self._chunks = json.load(f)
            except Exception as e:
                logger.warning("Chunk dosyası yüklenemedi: %s", e)
                self._chunks = []

    def _save_json_index(self):
        """Chunk metadata'sını JSON olarak kaydeder."""
        with self._lock:
            try:
                with open(self._chunks_path, "w", encoding="utf-8") as f:
                    json.dump(self._chunks, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("Chunk kaydedilemedi: %s", e)

    def _save_faiss_index(self):
        """FAISS indeksini diske kaydeder."""
        if self._is_faiss and self._index is not None:
            try:
                import faiss as faiss_lib

                faiss_lib.write_index(self._index, str(self._index_path))
                logger.debug("FAISS indeks kaydedildi (%d vektör)", self._index.ntotal)
            except Exception as e:
                logger.error("FAISS indeks kaydedilemedi: %s", e)

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """Vektörleri L2 normalize eder (kosinüs benzerliği için)."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms

    # ── Dışa Dönük API ─────────────────────────────────────────

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Chunk'ları vektör deposuna ekler.

        Args:
            chunks: {"text": ..., "metadata": {...}} şeklinde chunk listesi.

        Returns:
            Eklenen chunk sayısı.
        """
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        vectors = self.embedder.encode(texts)
        vectors = self._normalize(vectors)

        with self._lock:
            start_idx = len(self._chunks)
            for i, chunk in enumerate(chunks):
                chunk["metadata"]["vector_id"] = start_idx + i
                chunk["metadata"]["text_length"] = len(chunk["text"])
                self._chunks.append(chunk)

            if self._is_faiss and self._index is not None:
                self._index.add(vectors)
                self._save_faiss_index()

            if not self._is_faiss:
                self._save_json_index()

            # Embedding'leri .npy olarak kaydet (JSON modu için)
            if not self._is_faiss:
                npy_path = self._storage_dir / "embeddings.npy"
                if npy_path.exists():
                    existing = np.load(str(npy_path))
                    vectors = np.vstack([existing, vectors])
                np.save(str(npy_path), vectors)

        logger.info("%d chunk vektör deposuna eklendi.", len(chunks))
        return len(chunks)

    def search(
        self, query: Union[str, np.ndarray], top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Anlamsal arama yapar.

        Args:
            query: Arama sorgusu (metin) veya doğrudan vektör.
            top_k: Döndürülecek sonuç sayısı. None = config.top_k.

        Returns:
            Her biri {"text": ..., "metadata": {...}, "score": float} şeklinde
            sıralanmış sonuç listesi.
        """
        if top_k is None:
            top_k = self.config.top_k

        if not self._chunks:
            return []

        if isinstance(query, str):
            query_vec = self.embedder.encode_single(query)
        else:
            query_vec = query

        query_vec = self._normalize(query_vec.reshape(1, -1))

        if self._is_faiss and self._index is not None:
            return self._search_faiss(query_vec, top_k)
        return self._search_bruteforce(query_vec, top_k)

    def _search_faiss(self, query_vec: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        """FAISS indeksinde arama yapar."""
        import faiss as faiss_lib

        actual_k = min(top_k, len(self._chunks))
        if actual_k == 0:
            return []

        scores, indices = self._index.search(query_vec, actual_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            results.append(
                {
                    "text": chunk["text"],
                    "metadata": dict(chunk["metadata"]),
                    "score": float(score),
                }
            )
        return results

    def _search_bruteforce(
        self, query_vec: np.ndarray, top_k: int
    ) -> List[Dict[str, Any]]:
        """Kaba kuvvet (brute-force) kosinüs benzerliği araması."""
        npy_path = self._storage_dir / "embeddings.npy"
        if not npy_path.exists():
            return []

        embeddings = np.load(str(npy_path))
        if embeddings.shape[0] == 0:
            return []

        query_vec = query_vec.reshape(1, -1)
        similarities = embeddings @ query_vec.T
        similarities = similarities.flatten()

        actual_k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[::-1][:actual_k]

        results = []
        for idx in top_indices:
            chunk = self._chunks[idx]
            results.append(
                {
                    "text": chunk["text"],
                    "metadata": dict(chunk["metadata"]),
                    "score": float(similarities[idx]),
                }
            )
        return results

    def count(self) -> int:
        """Depodaki toplam vektör/chunk sayısı."""
        return len(self._chunks)

    def get_chunk(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """ID'ye göre chunk getirir."""
        if 0 <= vector_id < len(self._chunks):
            return self._chunks[vector_id]
        return None

    def remove_by_source(self, source: str) -> int:
        """
        Kaynak dosya adına göre chunk'ları siler.

        Args:
            source: Silinecek kaynak dosya adı.

        Returns:
            Silinen chunk sayısı.
        """
        with self._lock:
            before = len(self._chunks)
            self._chunks = [
                c for c in self._chunks if c["metadata"].get("source") != source
            ]
            removed = before - len(self._chunks)

            if removed > 0:
                self._rebuild_index()

            logger.info(
                "Kaynak '%s' silindi: %d chunk kaldırıldı.", source, removed
            )
            return removed

    def remove_by_doc_id(self, doc_id: str) -> int:
        """
        Belge ID'sine göre chunk'ları siler.

        Args:
            doc_id: Silinecek belge tanımlayıcısı.

        Returns:
            Silinen chunk sayısı.
        """
        with self._lock:
            before = len(self._chunks)
            self._chunks = [
                c for c in self._chunks if c["metadata"].get("doc_id") != doc_id
            ]
            removed = before - len(self._chunks)

            if removed > 0:
                self._rebuild_index()

            logger.info("doc_id '%s' silindi: %d chunk.", doc_id, removed)
            return removed

    def _rebuild_index(self):
        """İndeksi baştan oluşturur (silme işlemlerinden sonra)."""
        if not self._chunks:
            if self._is_faiss:
                import faiss as faiss_lib
                self._index = faiss_lib.IndexFlatIP(self._dimension)
                self._save_faiss_index()
            else:
                npy_path = self._storage_dir / "embeddings.npy"
                if npy_path.exists():
                    np.save(str(npy_path), np.empty((0, self._dimension)))
                self._save_json_index()
            return

        texts = [c["text"] for c in self._chunks]
        vectors = self.embedder.encode(texts)
        vectors = self._normalize(vectors)

        if self._is_faiss:
            import faiss as faiss_lib
            self._index = faiss_lib.IndexFlatIP(self._dimension)
            self._index.add(vectors)
            self._save_faiss_index()
        else:
            npy_path = self._storage_dir / "embeddings.npy"
            np.save(str(npy_path), vectors)
            self._save_json_index()

    def clear(self):
        """Tüm depoyu temizler."""
        with self._lock:
            self._chunks = []
            if self._is_faiss:
                import faiss as faiss_lib
                self._index = faiss_lib.IndexFlatIP(self._dimension)
                self._save_faiss_index()
            else:
                npy_path = self._storage_dir / "embeddings.npy"
                if npy_path.exists():
                    np.save(str(npy_path), np.empty((0, self._dimension)))
                self._save_json_index()
            logger.info("Vektör deposu temizlendi.")

    def get_all_sources(self) -> List[str]:
        """Depodaki tüm benzersiz kaynakları listeler."""
        sources: Set[str] = set()
        for c in self._chunks:
            src = c["metadata"].get("source", "")
            if src:
                sources.add(src)
        return sorted(sources)


# ═══════════════════════════════════════════════════════════════════
# WebCrawler - Web Sayfası Tarama
# ═══════════════════════════════════════════════════════════════════

class WebCrawler:
    """
    Web sayfalarını tarar ve metin çıkarır.

    Basit ve güvenli bir crawler:
    - requests ile sayfa indirme
    - BeautifulSoup ile metin çıkarma
    - Rate limiting (istekler arası bekleme)
    - Maksimum sayfa sayısı kontrolü

    Kullanım:
        crawler = WebCrawler()
        pages = crawler.crawl_single("https://ornek.com")
        pages = crawler.crawl_multiple(["url1", "url2"])
    """

    def __init__(
        self,
        user_agent: Optional[str] = None,
        request_delay: float = 1.0,
        max_pages_per_domain: int = 50,
        timeout: int = 30,
        max_content_length: int = 5 * 1024 * 1024,
    ):
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Shadowcat-RAG/1.0"
        )
        self.request_delay = request_delay
        self.max_pages_per_domain = max_pages_per_domain
        self.timeout = timeout
        self.max_content_length = max_content_length
        self._last_request_time: Dict[str, float] = {}

    def _rate_limit(self, domain: str):
        """Domain bazında rate limiting uygular."""
        last = self._last_request_time.get(domain, 0.0)
        elapsed = time.time() - last
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time[domain] = time.time()

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Bir web sayfasını indirir ve metin olarak döndürür.

        Args:
            url: İndirilecek sayfa adresi.

        Returns:
            Sayfanın düz metin içeriği veya hata durumunda None.
        """
        import requests

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc

            self._rate_limit(domain)

            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            }

            resp = requests.get(
                url, headers=headers, timeout=self.timeout, allow_redirects=True
            )
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                logger.warning("HTML dışı içerik atlandı: %s (%s)", url, content_type)
                return None

            if len(resp.content) > self.max_content_length:
                logger.warning("Sayfa çok büyük, atlandı: %s (%d bytes)", url, len(resp.content))
                return None

            raw = resp.text

            if _has_beautifulsoup:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(raw, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header",
                                 "noscript", "iframe", "form", "button"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
            else:
                text = re.sub(r"<[^>]+>", " ", raw)
                text = re.sub(r"\s+", " ", text).strip()

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            text = "\n".join(lines)

            logger.info("Sayfa indirildi: %s (%d karakter)", url, len(text))
            return text

        except requests.exceptions.RequestException as e:
            logger.warning("Sayfa indirilemedi: %s - %s", url, e)
            return None
        except Exception as e:
            logger.error("Beklenmeyen hata: %s - %s", url, e)
            return None

    def crawl_single(self, url: str) -> List[Dict[str, Any]]:
        """
        Tek bir web sayfasını crawler ve işlenmiş chunk'lar döndürür.

        Args:
            url: Taranacak sayfa adresi.

        Returns:
            Her biri {"text": ..., "metadata": {"source": url, ...}} chunk listesi.
        """
        text = self.fetch_page(url)
        if not text:
            return []

        indexer = DocumentIndexer()
        chunks = indexer.chunk_text(text, source=url)
        for chunk in chunks:
            chunk["metadata"]["source_type"] = "web"
            chunk["metadata"]["url"] = url
            chunk["metadata"]["crawl_time"] = datetime.now().isoformat()

        logger.info("Web sayfası işlendi: %s -> %d chunk", url, len(chunks))
        return chunks

    def crawl_multiple(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Birden çok web sayfasını tarar.

        Args:
            urls: Taranacak URL listesi.

        Returns:
            Tüm URL'lerden toplanmış chunk listesi.
        """
        all_chunks = []
        for url in urls:
            chunks = self.crawl_single(url)
            all_chunks.extend(chunks)
        return all_chunks


# ═══════════════════════════════════════════════════════════════════
# KnowledgeBase - Belge ve Bilgi Tabanı Yönetimi
# ═══════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """
    Bilgi tabanı yönetim sistemi.

    Belgeleri ekleme, silme, listeleme ve güncelleme işlemlerini yapar.
    VectorStore ve DocumentIndexer ile entegre çalışır.

    Kullanım:
        kb = KnowledgeBase(vector_store, document_indexer)
        kb.add_document("belge.pdf")
        kb.add_document("belge2.pdf")
        kb.list_documents()
        kb.remove_document("belge.pdf")
    """

    def __init__(
        self,
        vector_store: VectorStore,
        document_indexer: Optional[DocumentIndexer] = None,
    ):
        self.vector_store = vector_store
        self.indexer = document_indexer or DocumentIndexer()
        self._lock = Lock()

        self._documents_path = (
            vector_store.config.storage_path / "documents_meta.json"
        )
        self._documents: List[Dict[str, Any]] = []
        self._load_metadata()

    def _load_metadata(self):
        """Belge metadata'sını diskten yükler."""
        if self._documents_path.exists():
            try:
                with open(self._documents_path, "r", encoding="utf-8") as f:
                    self._documents = json.load(f)
                logger.info("%d belge metadata yüklendi.", len(self._documents))
            except Exception as e:
                logger.warning("Belge metadata yüklenemedi: %s", e)
                self._documents = []

    def _save_metadata(self):
        """Belge metadata'sını diske kaydeder."""
        with self._lock:
            try:
                with open(self._documents_path, "w", encoding="utf-8") as f:
                    json.dump(self._documents, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("Belge metadata kaydedilemedi: %s", e)

    def add_document(
        self, file_path: Union[str, Path], metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Bir belgeyi bilgi tabanına ekler.

        - Dosyayı okur, metin çıkarır
        - Chunk'lara böler
        - Vektör deposuna ekler
        - Metadata kaydeder

        Args:
            file_path: Eklenecek dosyanın yolu.
            metadata: Ek metadata (örn. {"kategori": "teknik_dokuman"}).

        Returns:
            Eklenen belge bilgisi.

        Raises:
            FileNotFoundError: Dosya mevcut değilse.
            ValueError: Dosya türü desteklenmiyorsa.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {path}")

        start = time.time()

        chunks = self.indexer.process_file(path)
        if not chunks:
            raise ValueError(f"Dosyadan metin çıkarılamadı: {path}")

        added_count = self.vector_store.add_chunks(chunks)

        doc_info: Dict[str, Any] = {
            "id": hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16],
            "filename": path.name,
            "path": str(path.absolute()),
            "file_type": path.suffix.lower().lstrip("."),
            "file_size": path.stat().st_size,
            "chunk_count": added_count,
            "added_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        with self._lock:
            self._documents.append(doc_info)
            self._save_metadata()

        elapsed = time.time() - start
        logger.info(
            "Belge eklendi: %s (%d chunk, %.2fs)",
            path.name,
            added_count,
            elapsed,
        )

        return doc_info

    def add_text(
        self, text: str, source: str = "inline_text", metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Ham metni bilgi tabanına ekler.

        Args:
            text: Eklenecek metin.
            source: Kaynak tanımlayıcı.
            metadata: Ek metadata.

        Returns:
            Eklenen belge bilgisi.
        """
        chunks = self.indexer.process_text(text, source=source)
        if not chunks:
            raise ValueError("Metin chunk'lara ayrılamadı.")

        added_count = self.vector_store.add_chunks(chunks)

        doc_info: Dict[str, Any] = {
            "id": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "filename": source,
            "path": source,
            "file_type": "text",
            "file_size": len(text),
            "chunk_count": added_count,
            "added_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        with self._lock:
            self._documents.append(doc_info)
            self._save_metadata()

        logger.info("Metin eklendi: %s (%d chunk)", source, added_count)
        return doc_info

    def add_web_page(self, url: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Bir web sayfasını bilgi tabanına ekler.

        Args:
            url: Web sayfası adresi.
            metadata: Ek metadata.

        Returns:
            Eklenen belge bilgisi.
        """
        crawler = WebCrawler()
        chunks = crawler.crawl_single(url)
        if not chunks:
            raise ValueError(f"Web sayfası işlenemedi: {url}")

        added_count = self.vector_store.add_chunks(chunks)

        doc_info: Dict[str, Any] = {
            "id": hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
            "filename": url.rsplit("/", 1)[-1] if "/" in url else url,
            "path": url,
            "file_type": "web",
            "file_size": sum(len(c["text"]) for c in chunks),
            "chunk_count": added_count,
            "added_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": {"url": url, **(metadata or {})},
        }

        with self._lock:
            self._documents.append(doc_info)
            self._save_metadata()

        logger.info("Web sayfası eklendi: %s (%d chunk)", url, added_count)
        return doc_info

    def remove_document(self, filename: str) -> bool:
        """
        Bir belgeyi bilgi tabanından kaldırır.

        Args:
            filename: Kaldırılacak dosya adı (tam yol veya dosya adı).

        Returns:
            Başarılıysa True.
        """
        with self._lock:
            matching = [
                d for d in self._documents
                if d["filename"] == filename or d["path"] == filename
            ]
            if not matching:
                logger.warning("Belge bulunamadı: %s", filename)
                return False

            removed = 0
            for doc in matching:
                source = doc["path"]
                r = self.vector_store.remove_by_source(source)
                removed += r
                self._documents = [d for d in self._documents if d["id"] != doc["id"]]

            self._save_metadata()

            logger.info(
                "Belge kaldırıldı: %s (%d chunk silindi)", filename, removed
            )
            return True

    def remove_by_id(self, doc_id: str) -> bool:
        """
        Belge ID'sine göre belge kaldırır.

        Args:
            doc_id: Kaldırılacak belgenin ID'si.

        Returns:
            Başarılıysa True.
        """
        with self._lock:
            matching = [d for d in self._documents if d["id"] == doc_id]
            if not matching:
                logger.warning("Belge ID bulunamadı: %s", doc_id)
                return False

            doc = matching[0]
            source = doc["path"]
            self.vector_store.remove_by_source(source)
            self._documents = [d for d in self._documents if d["id"] != doc_id]
            self._save_metadata()

            logger.info("Belge kaldırıldı (ID): %s - %s", doc_id, doc["filename"])
            return True

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        Bilgi tabanındaki tüm belgeleri listeler.

        Returns:
            Belge metadata listesi.
        """
        with self._lock:
            docs = sorted(
                self._documents,
                key=lambda d: d.get("added_at", ""),
                reverse=True,
            )
            total = sum(d.get("chunk_count", 0) for d in docs)
            return [
                {
                    "id": d["id"],
                    "filename": d["filename"],
                    "file_type": d["file_type"],
                    "file_size": d["file_size"],
                    "chunk_count": d["chunk_count"],
                    "added_at": d["added_at"],
                    "metadata": d.get("metadata", {}),
                }
                for d in docs
            ] + [{"_summary": {"total_documents": len(docs), "total_chunks": total}}]

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Belge ID'sine göre belge bilgisini getirir.

        Args:
            doc_id: Belge tanımlayıcısı.

        Returns:
            Belge metadata'sı veya None.
        """
        for d in self._documents:
            if d["id"] == doc_id:
                return dict(d)
        return None

    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Bilgi tabanında anlamsal arama yapar.

        Args:
            query: Arama sorgusu.
            top_k: Sonuç sayısı.

        Returns:
            Sıralanmış sonuç listesi.
        """
        results = self.vector_store.search(query, top_k=top_k)
        for r in results:
            src = r["metadata"].get("source", "")
            doc_id = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
            r["metadata"]["doc_id"] = doc_id
        return results

    def get_document_count(self) -> int:
        """Bilgi tabanındaki belge sayısını döndürür."""
        return len(self._documents)

    def get_total_chunks(self) -> int:
        """Toplam chunk sayısını döndürür."""
        return sum(d.get("chunk_count", 0) for d in self._documents)

    def clear(self):
        """Bilgi tabanını tamamen temizler."""
        self.vector_store.clear()
        with self._lock:
            self._documents = []
            self._save_metadata()
        logger.info("Bilgi tabanı temizlendi.")


# ═══════════════════════════════════════════════════════════════════
# RAGEngine - Ana RAG Sistemi
# ═══════════════════════════════════════════════════════════════════

class RAGEngine:
    """
    Ana RAG (Retrieval-Augmented Generation) motoru.

    Tüm bileşenleri birleştirir:
    - Belge işleme (DocumentIndexer)
    - Vektör arama (VectorStore)
    - Bağlam yönetimi (context augmentation)
    - Bilgi tabanı (KnowledgeBase)

    Kullanım:
        engine = RAGEngine()
        engine.initialize()

        # Belge ekle
        engine.add_document("teknik_dokuman.pdf")

        # Sorgula
        context = engine.query("makine öğrenmesi nedir?")

        # Sohbet augmentasyonu
        augmented = engine.augment_chat("Kullanıcı: soru...")
    """

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._initialized = False

        # Bileşenler (initialize çağrılana kadar None)
        self.embedder: Optional[EmbeddingModel] = None
        self.indexer: Optional[DocumentIndexer] = None
        self.vector_store: Optional[VectorStore] = None
        self.knowledge_base: Optional[KnowledgeBase] = None

        logger.info("RAGEngine oluşturuldu (storage: %s)", self.config.storage_path)

    def initialize(self):
        """
        RAG motorunu başlatır.

        Tüm alt bileşenleri yükler:
        1. Embedding model
        2. Document indexer
        3. Vector store
        4. Knowledge base

        Bu metodu kullanmadan önce config değiştirilebilir.
        """
        if self._initialized:
            logger.warning("RAGEngine zaten başlatılmış.")
            return

        self.config.storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "RAGEngine başlatılıyor (embedding=%s, faiss=%s, ollama=%s)...",
            self.config.embedding_model,
            self.config.use_faiss,
            self.config.use_ollama_embeddings,
        )

        self.embedder = EmbeddingModel(self.config)
        self.indexer = DocumentIndexer(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        self.vector_store = VectorStore(self.config, self.embedder)
        self.knowledge_base = KnowledgeBase(self.vector_store, self.indexer)

        self._initialized = True
        logger.info(
            "RAGEngine başlatıldı. Depoda %d vektör, %d belge var.",
            self.vector_store.count(),
            self.knowledge_base.get_document_count(),
        )

    def _ensure_initialized(self):
        """Motor başlatılmamışsa hata fırlatır."""
        if not self._initialized:
            raise RuntimeError(
                "RAGEngine başlatılmamış. Lütfen initialize() çağırın."
            )

    # ── Belge Yönetimi ──────────────────────────────────────────

    def add_document(
        self, file_path: Union[str, Path], metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Bir belgeyi RAG sistemine ekler.

        Args:
            file_path: Dosya yolu.
            metadata: Ek metadata.

        Returns:
            Belge bilgisi.
        """
        self._ensure_initialized()
        return self.knowledge_base.add_document(file_path, metadata=metadata)

    def add_text(
        self, text: str, source: str = "inline_text", metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Ham metni RAG sistemine ekler.

        Args:
            text: Metin içeriği.
            source: Kaynak adı.
            metadata: Ek metadata.

        Returns:
            Belge bilgisi.
        """
        self._ensure_initialized()
        return self.knowledge_base.add_text(text, source=source, metadata=metadata)

    def add_web_page(self, url: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Web sayfasını RAG sistemine ekler.

        Args:
            url: Sayfa adresi.
            metadata: Ek metadata.

        Returns:
            Belge bilgisi.
        """
        self._ensure_initialized()
        return self.knowledge_base.add_web_page(url, metadata=metadata)

    def remove_document(self, filename: str) -> bool:
        """Belge kaldırır."""
        self._ensure_initialized()
        return self.knowledge_base.remove_document(filename)

    def list_documents(self) -> List[Dict[str, Any]]:
        """Belgeleri listeler."""
        self._ensure_initialized()
        return self.knowledge_base.list_documents()

    # ── Arama ve Sorgulama ─────────────────────────────────────

    def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        include_scores: bool = True,
    ) -> Dict[str, Any]:
        """
        RAG sorgusu yapar.

        En alakalı belge parçalarını bulur ve yapılandırılmış
        şekilde döndürür.

        Args:
            query_text: Sorgu metni.
            top_k: Döndürülecek sonuç sayısı.
            include_scores: Skor bilgisi eklensin mi.

        Returns:
            {
                "query": ...,
                "results": [...],
                "total_results": ...,
                "context": "birleştirilmiş bağlam metni",
                "sources": [...]
            }
        """
        self._ensure_initialized()

        top_k = top_k or self.config.top_k
        results = self.vector_store.search(query_text, top_k=top_k)

        for r in results:
            src = r["metadata"].get("source", "")
            r["metadata"]["doc_id"] = hashlib.sha256(
                src.encode("utf-8")
            ).hexdigest()[:16]

        context = self._build_context(results)
        sources = list(
            set(
                r["metadata"].get("source", "bilinmeyen")
                for r in results
                if r["metadata"].get("source")
            )
        )

        response: Dict[str, Any] = {
            "query": query_text,
            "results": results if include_scores else [
                {"text": r["text"], "metadata": r["metadata"]} for r in results
            ],
            "total_results": len(results),
            "context": context,
            "sources": sources,
        }

        logger.debug(
            "Sorgu: '%s' -> %d sonuç, %d kaynak",
            query_text[:50],
            len(results),
            len(sources),
        )

        return response

    def search(
        self, query: str, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Basit arama (KnowledgeBase.search wrapper).

        Args:
            query: Arama sorgusu.
            top_k: Sonuç sayısı.

        Returns:
            Sonuç listesi.
        """
        self._ensure_initialized()
        return self.knowledge_base.search(query, top_k=top_k)

    def _build_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Arama sonuçlarından birleştirilmiş bağlam metni oluşturur.

        Args:
            results: Arama sonuçları (skor sıralı).

        Returns:
            LLM prompt'una eklenmeye hazır bağlam metni.
        """
        if not results:
            return ""

        chunks_to_use = results[: self.config.max_context_chunks]
        token_estimate = 0
        context_parts = []

        for chunk in chunks_to_use:
            text = chunk["text"].strip()
            source = chunk["metadata"].get("source", "bilinmeyen")

            if not text:
                continue

            part = f"[Kaynak: {source}]\n{text}"
            estimated_tokens = len(part) // 4

            if (
                self.config.max_context_tokens > 0
                and token_estimate + estimated_tokens > self.config.max_context_tokens
            ):
                allowed_chars = (
                    self.config.max_context_tokens - token_estimate
                ) * 4
                if allowed_chars > 50:
                    part = f"[Kaynak: {source}]\n{text[:allowed_chars]}..."
                else:
                    break

            context_parts.append(part)
            token_estimate += estimated_tokens

        if not context_parts:
            return ""

        context = "\n\n---\n\n".join(context_parts)
        header = (
            "Aşağıdaki bilgi tabanı belgeleri kullanıcının sorusuyla alakalıdır.\n"
            "Bu bilgileri kullanarak soruyu cevapla. Emin değilsen 'bilmiyorum' de.\n"
            f"\n{'='*60}\n\n"
        )
        return header + context

    # ── Konuşma Bağlamı Augmentasyonu ──────────────────────────

    def augment_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_context_length: int = 2000,
    ) -> Dict[str, Any]:
        """
        Kullanıcı mesajını RAG bağlamıyla zenginleştirir.

        - Kullanıcı mesajıyla alakalı belge parçalarını bulur
        - Bunları sistem prompt'una ekler
        - Konuşma geçmişiyle birleştirir

        Args:
            user_message: Kullanıcının son mesajı.
            conversation_history: Geçmiş konuşma ({"role", "content"} listesi).
            system_prompt: Mevcut sistem prompt'u (None=default).
            max_context_length: RAG bağlamı için maksimum karakter.

        Returns:
            {
                "augmented_prompt": zenginleştirilmiş prompt,
                "rag_context": kullanılan RAG bağlamı,
                "sources": kaynak listesi,
                "original_message": orijinal mesaj
            }
        """
        self._ensure_initialized()

        # Alakalı belgeleri bul
        search_results = self.vector_store.search(
            user_message, top_k=self.config.top_k
        )
        if not search_results:
            return {
                "augmented_prompt": user_message,
                "rag_context": "",
                "sources": [],
                "original_message": user_message,
            }

        # Bağlam metnini oluştur (karakter sınırı)
        context_parts = []
        char_count = 0
        sources = []

        for r in search_results:
            source = r["metadata"].get("source", "bilinmeyen")
            text = r["text"].strip()
            entry = f"[{source}]\n{text}"

            if char_count + len(entry) > max_context_length:
                remaining = max_context_length - char_count
                if remaining > 100:
                    entry = f"[{source}]\n{text[:remaining]}..."
                else:
                    break

            context_parts.append(entry)
            char_count += len(entry)
            if source not in sources:
                sources.append(source)

        rag_context = "\n\n---\n\n".join(context_parts)

        # Sistem prompt'u oluştur
        default_system = (
            "Sen Shadowcat/Shadowcat AI asistanısın. "
            "Kullanıcıya yardım etmek için aşağıdaki bilgi tabanını kullan."
        )
        system = system_prompt or default_system

        augmented_system = (
            f"{system}\n\n"
            f"── BİLGİ TABANI ──\n"
            f"{rag_context}\n"
            f"── ─────────── ──\n\n"
            f"Yukarıdaki bilgileri kullanarak kullanıcıya en doğru yanıtı ver. "
            f"Emin değilsen 'Bilgi tabanımda bu konuda yeterli bilgi yok' de."
        )

        # Konuşma geçmişini birleştir
        if conversation_history:
            messages = [{"role": "system", "content": augmented_system}]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            augmented_prompt = messages
        else:
            augmented_prompt = [
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": user_message},
            ]

        return {
            "augmented_prompt": augmented_prompt,
            "rag_context": rag_context,
            "sources": sources,
            "original_message": user_message,
        }

    def format_context_for_prompt(self, query: str) -> str:
        """
        Sorgu için biçimlendirilmiş bağlam metni döndürür.

        Doğrudan LLM prompt'una eklenmek için kullanılır.

        Args:
            query: Sorgu metni.

        Returns:
            Biçimlendirilmiş bağlam metni.
        """
        result = self.query(query)
        return result.get("context", "")

    # ── Durum ve İstatistik ────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """RAG sistemi istatistiklerini döndürür."""
        if not self._initialized:
            return {"status": "not_initialized"}

        return {
            "status": "ready",
            "vector_count": self.vector_store.count(),
            "document_count": self.knowledge_base.get_document_count(),
            "total_chunks": self.knowledge_base.get_total_chunks(),
            "config": self.config.to_dict(),
            "faiss_enabled": self.vector_store._is_faiss,
        }

    def get_status_summary(self) -> str:
        """RAG sistemi durum özetini döndürür (insan tarafından okunabilir)."""
        stats = self.get_stats()
        if stats.get("status") != "ready":
            return "RAG sistemi başlatılmamış."

        lines = [
            "RAG Sistemi Aktif",
            f"  Belge Sayısı: {stats['document_count']}",
            f"  Chunk Sayısı: {stats['total_chunks']}",
            f"  Vektör Sayısı: {stats['vector_count']}",
            f"  Depolama: {'FAISS' if stats.get('faiss_enabled') else 'JSON+NumPy'}",
            f"  Embedding: {'Ollama' if self.config.use_ollama_embeddings else 'sentence-transformers'}",
            f"  Model: {self.config.ollama_embedding_model if self.config.use_ollama_embeddings else self.config.embedding_model}",
            f"  Depo: {self.config.storage_path}",
        ]
        return "\n".join(lines)

    def save_state(self):
        """RAG sistemi durumunu diske kaydeder."""
        self._ensure_initialized()

        config_path = self.config.storage_path / "rag_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info("RAG durumu kaydedildi: %s", self.config.storage_path)

    @classmethod
    def load_state(cls, storage_path: Union[str, Path]) -> "RAGEngine":
        """
        Kaydedilmiş RAG durumunu yükler.

        Args:
            storage_path: Depolama dizini.

        Returns:
            Başlatılmış RAGEngine örneği.
        """
        storage_path = Path(storage_path)
        config_path = storage_path / "rag_config.json"

        if not config_path.exists():
            logger.warning("Kayıtlı config bulunamadı, varsayılanla başlatılıyor.")
            engine = cls()
            engine.initialize()
            return engine

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        config = RAGConfig.from_dict(config_data)
        config.storage_path = storage_path
        engine = cls(config)
        engine.initialize()

        return engine

    def shutdown(self):
        """RAG motorunu kapatır ve kaynakları temizler."""
        if self._initialized:
            self.save_state()
            if self.embedder:
                self.embedder.unload_model()
            self._initialized = False
            logger.info("RAGEngine kapatıldı.")


# ═══════════════════════════════════════════════════════════════════
# get_rag_engine() - Global Erişim Fonksiyonu
# ═══════════════════════════════════════════════════════════════════

_rag_engine_instance: Optional[RAGEngine] = None
_rag_engine_lock = Lock()


def get_rag_engine(
    config: Optional[RAGConfig] = None, auto_initialize: bool = True
) -> RAGEngine:
    """
    Global RAGEngine instance'ı döndürür (Singleton pattern).

    Args:
        config: RAG yapılandırması (ilk çağrıda kullanılır).
        auto_initialize: Otomatik başlatma.

    Returns:
        RAGEngine örneği.
    """
    global _rag_engine_instance

    with _rag_engine_lock:
        if _rag_engine_instance is None:
            if config is None:
                config = RAGConfig()
            _rag_engine_instance = RAGEngine(config)
            if auto_initialize:
                _rag_engine_instance.initialize()
        elif config is not None and auto_initialize:
            if not _rag_engine_instance._initialized:
                _rag_engine_instance.initialize()

        return _rag_engine_instance


def reset_rag_engine():
    """Global RAGEngine instance'ını sıfırlar."""
    global _rag_engine_instance
    with _rag_engine_lock:
        if _rag_engine_instance is not None:
            _rag_engine_instance.shutdown()
            _rag_engine_instance = None
    logger.info("RAGEngine global instance sıfırlandı.")


# ═══════════════════════════════════════════════════════════════════
# Ana Blok - Örnek Kullanım ve Test
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  Shadowcat RAG Sistemi - Test / Örnek Kullanım")
    print("═" * 60)

    # Yapılandırma
    config = RAGConfig(
        storage_path="rag_test_storage",
        chunk_size=512,
        chunk_overlap=64,
        use_faiss=True,  # FAISS yoksa JSON'a düşer
        top_k=5,
        device="cpu",
    )

    # RAG Motorunu başlat
    engine = RAGEngine(config)
    try:
        engine.initialize()
    except Exception as e:
        print(f"\nRAG motoru başlatılamadı: {e}")
        print("   Gerekli paketleri yükleyin:")
        print("   pip install sentence-transformers faiss-cpu PyPDF2 beautifulsoup4")
        print("\n   Veya Ollama ile kullanmak için:")
        print("   config.use_ollama_embeddings = True")
        exit(1)

    print("\n" + engine.get_status_summary())
    print()

    # Test metni ekle
    test_text = """
    Shadowcat (Shadowcat AI), yapay zeka destekli bir masaüstü asistanıdır.
    Kullanıcıların bilgisayarlarında sesli ve yazılı komutlarla etkileşime girer.
    
    Özellikler:
    - Doğal dil işleme (NLP) ile kullanıcı komutlarını anlama
    - Uygulama açma/kapatma
    - Dosya yönetimi (oluşturma, düzenleme, silme)
    - Web arama ve bilgi toplama
    - Kod yazma ve çalıştırma (Python sandbox)
    - Ekran görüntüsü analizi
    - Sesli yanıt (TTS)
    - Model yönlendirme (Ollama entegrasyonu)
    
    Shadowcat, Ollama üzerinden çalışan çeşitli açık kaynak modelleri
    kullanır: Llama 3.1, Qwen 2.5 Coder, DeepSeek R1 ve LLaVA.
    """

    print("Test metni ekleniyor...")
    doc_info = engine.add_text(test_text, source="glassescat_tanitim")
    print(f"   Eklendi: {doc_info['filename']} ({doc_info['chunk_count']} chunk)")

    # Sorgu testi
    print("\nSorgu testi: 'Shadowcat hangi özelliklere sahip?'")
    result = engine.query("Shadowcat hangi özelliklere sahip?")
    
    print(f"   Sonuç sayısı: {result['total_results']}")
    for i, r in enumerate(result["results"][:3], 1):
        print(f"   [{i}] Skor: {r['score']:.4f}")
        print(f"       {r['text'][:100]}...")

    # Bağlam augmentasyonu testi
    print("\nSohbet augmentasyonu testi:")
    augmented = engine.augment_chat(
        "Shadowcat hangi modelleri kullanıyor?",
        max_context_length=1500,
    )
    print(f"   Kaynaklar: {augmented['sources']}")
    print(f"   Bağlam uzunluğu: {len(augmented['rag_context'])} karakter")

    # Belge listesi
    print("\nBilgi tabanı:")
    docs = engine.list_documents()
    for d in docs:
        if "_summary" in d:
            print(f"   Toplam: {d['_summary']['total_documents']} belge, {d['_summary']['total_chunks']} chunk")
        else:
            print(f"   - {d['filename']} ({d['file_type']}, {d['chunk_count']} chunk)")

    # Temizlik
    print("\nTest depolaması temizleniyor...")
    engine.knowledge_base.clear()
    engine.shutdown()

    # Test dizinini temizle
    import shutil
    test_dir = Path("rag_test_storage")
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\nTest başarıyla tamamlandı!")
