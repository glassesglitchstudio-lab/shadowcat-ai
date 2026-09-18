from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile

import logging

logger = logging.getLogger("routes.rag")
router = APIRouter()

def get_rag():
    try:
        from rag_system import RAGEngine
        return RAGEngine()
    except (ImportError, Exception) as e:
        logger.warning(f"RAG yüklenemedi: {e}")
        return None

class RAGSearchQuery(BaseModel):
    query: str
    top_k: int = 5

class RAGChatQuery(BaseModel):
    query: str
    context_docs: Optional[List[str]] = None

@router.get("/status")
async def rag_status():
    """RAG sistemi durumu"""
    rag = get_rag()
    if not rag:
        return {"available": False, "error": "RAG sistemi mevcut değil"}
    return {"available": True, "status": "active"}

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Belge yükle (PDF, TXT, MD, HTML)"""
    rag = get_rag()
    if not rag:
        raise HTTPException(status_code=503, detail="RAG sistemi mevcut değil")

    allowed_types = [".pdf", ".txt", ".md", ".html", ".csv"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya türü: {ext}")

    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        rag.index_file(tmp_path)
        os.unlink(tmp_path)
        return {"message": f"{file.filename} yüklendi ve indekslendi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_documents(query: RAGSearchQuery):
    """Vektör araması"""
    rag = get_rag()
    if not rag:
        raise HTTPException(status_code=503, detail="RAG sistemi mevcut değil")
    try:
        results = rag.search(query.query, top_k=query.top_k)
        return {"results": results, "query": query.query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def rag_chat(query: RAGChatQuery):
    """RAG destekli sohbet"""
    rag = get_rag()
    if not rag:
        raise HTTPException(status_code=503, detail="RAG sistemi mevcut değil")
    try:
        context = rag.search(query.query, top_k=3)
        context_text = "\n".join([doc.get("content", "") for doc in context])

        from routes.chat import ollama_stream
        prompt = f"Bağlam:\n{context_text}\n\nSoru: {query.query}\n\nCevap:"

        full_response = ""
        async for token in ollama_stream(prompt):
            full_response += token

        return {"response": full_response, "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents")
async def list_documents():
    """Yüklü belgeleri listele"""
    rag = get_rag()
    if not rag:
        return {"documents": []}
    try:
        docs = rag.list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.warning(f"Belge listelenemedi: {e}")
        return {"documents": []}

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Belge sil (doc_id ile)"""
    rag = get_rag()
    if not rag:
        raise HTTPException(status_code=503, detail="RAG sistemi mevcut değil")
    try:
        removed = rag.remove_by_id(doc_id)
        if removed:
            return {"message": f"Belge silindi: {doc_id}"}
        # doc_id ile bulunamazsa filename ile dene
        removed = rag.remove_document(doc_id)
        if removed:
            return {"message": f"Belge silindi: {doc_id}"}
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def rag_stats():
    """RAG indeks istatistikleri"""
    rag = get_rag()
    if not rag:
        return {"available": False, "total_documents": 0, "total_chunks": 0}
    try:
        stats = rag.get_stats()
        return {"available": True, **stats}
    except Exception as e:
        logger.warning(f"RAG istatistikleri alınamadı: {e}")
        return {"available": True, "total_documents": 0, "total_chunks": 0}
