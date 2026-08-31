"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   SHADOWCAT - WEB AGENT (Otonom Web Tarayıcı) ║
║                                                               ║
║   AI'ın web'de gezinmesini, bilgi toplamasını ve             ║
║   etkileşimde bulunmasını sağlar.                            ║
║                                                               ║
║   Özellikler:                                                 ║
║   - Web sayfası içeriğini getir ve analiz et                 ║
║   - Bağlantıları bul ve takip et                             ║
║   - Sayfadaki metinleri çıkar                                 ║
║   - Form elemanlarını bul                                     ║
║   - Sayfa özeti çıkar                                        ║
║   - Google/DuckDuckGo'da ara                                 ║
║   - İndirme linklerini bul                                   ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

logger = logging.getLogger("GlassescatWebAgent")

# ─────────────────────────────────────────────────────────────
# İsteğe bağlı bağımlılıklar
# ─────────────────────────────────────────────────────────────

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import webbrowser
    WEBBROWSER_OK = True
except ImportError:
    WEBBROWSER_OK = False

try:
    from duckduckgo_search import DDGS
    DDGS_OK = True
except ImportError:
    DDGS_OK = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False

# ─────────────────────────────────────────────────────────────
# VERİ SINIFLARI
# ─────────────────────────────────────────────────────────────

@dataclass
class PageLink:
    url: str
    text: str = ""
    is_internal: bool = True

@dataclass
class PageInfo:
    url: str
    title: str = ""
    text: str = ""
    html: str = ""
    links: List[PageLink] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    headers: Dict = field(default_factory=dict)
    status_code: int = 0
    load_time: float = 0.0
    word_count: int = 0
    error: Optional[str] = None

# ─────────────────────────────────────────────────────────────
# WEB AGENT
# ─────────────────────────────────────────────────────────────

class WebAgent:
    """
    Otonom web gezinti sistemi.
    
    AI'ın web'de bilgi toplaması, sayfaları analiz etmesi
    ve içerik çıkarması için araçlar sağlar.
    
    Kullanım:
        agent = WebAgent()
        
        # Sayfa getir
        page = agent.fetch_page("https://example.com")
        print(page.title, page.text[:200])
        
        # Web'de ara
        results = agent.search("yapay zeka haberleri")
        
        # Sayfayı tarayıcıda aç
        agent.open_in_browser("https://github.com")
    """
    
    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {"User-Agent": self.user_agent}
        self.timeout = 15
        self.max_page_size = 2 * 1024 * 1024  # 2MB limit
        
        # Önbellek
        self.cache = {}
        self.cache_ttl = 300  # 5 dakika
        self.max_cache = 50
        
        # Rate limiting
        self._last_request = 0
        self._min_delay = 1.0  # saniye
        
        # Ziyaret geçmişi
        self.visit_history: List[Dict] = []
        self.max_history = 100
    
    def fetch_page(self, url: str, timeout: int = None) -> PageInfo:
        """
        Bir web sayfasını getir ve analiz et.
        
        Args:
            url: Sayfa URL'si
            timeout: Zaman aşımı (saniye)
        
        Returns:
            PageInfo: Sayfa bilgileri
        """
        _timeout = timeout or self.timeout
        
        # URL düzeltme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        # Önbellek kontrolü
        cache_key = url
        if cache_key in self.cache:
            cached_time, cached_page = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_page
        
        page = PageInfo(url=url)
        start_time = time.time()
        
        # Rate limiting
        self._rate_limit()
        
        # İstek
        if not REQUESTS_OK:
            page.error = "requests modülü kurulu değil"
            return page
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=_timeout,
                stream=True
            )
            
            page.status_code = response.status_code
            page.headers = dict(response.headers)
            
            if response.status_code != 200:
                page.error = f"HTTP {response.status_code}"
                self._add_to_history(url, page)
                return page
            
            # İçeriği oku (boyut limiti ile)
            content = b""
            for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                if isinstance(chunk, bytes):
                    content += chunk
                else:
                    content += chunk.encode('utf-8', errors='replace')
                if len(content) > self.max_page_size:
                    break
            
            # Metin olarak çöz
            try:
                html = content.decode('utf-8', errors='replace')
            except:
                html = str(content)
            
            page.html = html
            page.load_time = time.time() - start_time
            
            # Parse et
            self._parse_html(page)
            
            # Önbelleğe ekle
            self.cache[cache_key] = (time.time(), page)
            if len(self.cache) > self.max_cache:
                # En eski önbelleği temizle
                oldest = min(self.cache.keys(), key=lambda k: self.cache[k][0])
                del self.cache[oldest]
        
        except requests.exceptions.Timeout:
            page.error = f"Zaman aşımı ({_timeout}s)"
        except requests.exceptions.ConnectionError:
            page.error = "Bağlantı hatası"
        except Exception as e:
            page.error = str(e)
        
        page.load_time = time.time() - start_time
        self._add_to_history(url, page)
        
        return page
    
    def fetch_page_js(self, url: str, timeout: int = 30) -> PageInfo:
        """
        Playwright ile JS-render edilmiş sayfayı getir.
        Normal fetch_page JS içeriğini alamazsa bunu dene.
        """
        if not PLAYWRIGHT_OK:
            return self.fetch_page(url, timeout)
        
        page = PageInfo(url=url)
        start_time = time.time()
        
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1280, "height": 720}
                )
                ctx = context.new_page()
                ctx.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                page.html = ctx.content()
                page.title = ctx.title()
                browser.close()
            
            page.status_code = 200
            page.load_time = time.time() - start_time
            self._parse_html(page)
            
            if not page.text:
                self._regex_parse(page)
            
            return page
        except Exception as e:
            page.error = f"Playwright hatası: {e}"
            page.load_time = time.time() - start_time
            return page
    
    def _parse_html(self, page: PageInfo):
        """HTML sayfasını parse et"""
        if not BS4_OK:
            # Basit regex parse
            self._regex_parse(page)
            return
        
        try:
            soup = BeautifulSoup(page.html, 'html.parser')
        except:
            self._regex_parse(page)
            return
        
        # Başlık
        if soup.title:
            page.title = soup.title.get_text(strip=True)
        
        # Metin içeriği (script/style temizlenmiş)
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        page.text = soup.get_text(separator='\n', strip=True)
        page.word_count = len(page.text.split())
        
        # Bağlantılar
        base_url = page.url
        seen_urls = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            full_url = urljoin(base_url, href)
            
            # Aynı URL'yi tekrar ekleme
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Dahili/harici kontrol
            parsed_base = urlparse(base_url)
            parsed_link = urlparse(full_url)
            is_internal = parsed_base.netloc == parsed_link.netloc
            
            page.links.append(PageLink(
                url=full_url,
                text=a_tag.get_text(strip=True)[:100],
                is_internal=is_internal
            ))
        
        # Görseller
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            full_src = urljoin(base_url, src)
            if full_src not in page.images:
                page.images.append(full_src)
    
    def _regex_parse(self, page: PageInfo):
        """BeautifulSoup yoksa regex ile basit parse"""
        html = page.html
        
        # Başlık
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            page.title = title_match.group(1).strip()
        
        # Metin (basit HTML temizleme)
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        page.text = text[:10000]  # İlk 10K karakter
        page.word_count = len(page.text.split())
        
        # Bağlantılar
        for match in re.finditer(r'<a[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>', 
                                html, re.IGNORECASE | re.DOTALL):
            href = match.group(1)
            text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            
            parsed_base = urlparse(page.url)
            parsed_link = urlparse(href)
            is_internal = parsed_base.netloc == parsed_link.netloc
            
            page.links.append(PageLink(url=href, text=text[:100], is_internal=is_internal))
    
    def search(self, query: str, max_results: int = 10, engine: str = "auto") -> List[Dict]:
        """
        Web'de arama yap.
        
        Args:
            query: Arama sorgusu
            max_results: Maksimum sonuç sayısı
            engine: Arama motoru (auto, duckduckgo, google)
        
        Returns:
            List[Dict]: Arama sonuçları
        """
        # Önce duckduckgo_search kütüphanesini dene
        if DDGS_OK:
            try:
                return self._search_ddgs(query, max_results)
            except Exception as e:
                logger.debug(f"DDGS hatası, scraping fallback: {e}")
        if engine == "google":
            return self._search_google(query, max_results)
        return self._search_duckduckgo(query, max_results)
    
    def _search_ddgs(self, query: str, max_results: int) -> List[Dict]:
        """duckduckgo_search kütüphanesi ile ara (sağlam API)"""
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
        return results
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict]:
        """DuckDuckGo'da ara (HTML scraping yedek)"""
        if not REQUESTS_OK:
            return [{"error": "requests modülü gerekli"}]
        
        self._rate_limit()
        
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                headers=self.headers,
                timeout=10
            )
            
            if resp.status_code != 200:
                return []
            
            results = []
            html = resp.text
            
            for match in re.finditer(
                r'<a[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>(?:<[^>]+>)*([^<]*)',
                html, re.IGNORECASE
            ):
                url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                
                if url and not url.startswith('//'):
                    results.append({
                        "title": title or url,
                        "url": url,
                        "snippet": ""
                    })
                    
                    if len(results) >= max_results:
                        break
            
            return results
        
        except Exception as e:
            logger.warning(f"DuckDuckGo arama hatası: {e}")
            return []
    
    def _search_google(self, query: str, max_results: int) -> List[Dict]:
        """Google'da ara (rate limit riski var)"""
        if not REQUESTS_OK:
            return []
        
        self._rate_limit()
        
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=tr"
            resp = requests.get(search_url, headers=self.headers, timeout=10)
            
            if resp.status_code != 200:
                return self._search_duckduckgo(query, max_results)
            
            results = []
            
            if BS4_OK:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for g in soup.find_all('div', class_='g')[:max_results]:
                    link = g.find('a')
                    if link and link.get('href'):
                        url = link.get('href')
                        if url.startswith('/url?q='):
                            url = url.split('/url?q=')[1].split('&')[0]
                        
                        title_tag = g.find('h3')
                        title = title_tag.get_text(strip=True) if title_tag else url
                        
                        snippet_tag = g.find('div', class_=['VwiC3b', 'st'])
                        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                        
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet
                        })
            
            return results if results else self._search_duckduckgo(query, max_results)
        
        except Exception as e:
            logger.warning(f"Google arama hatası: {e}")
            return self._search_duckduckgo(query, max_results)
    
    def extract_links(self, url: str, filter_pattern: str = None) -> List[PageLink]:
        """Bir sayfadaki bağlantıları çıkar"""
        page = self.fetch_page(url)
        if page.error:
            return []
        
        if filter_pattern:
            return [
                link for link in page.links
                if re.search(filter_pattern, link.url, re.IGNORECASE)
            ]
        
        return page.links
    
    def search_and_fetch(self, query: str, max_pages: int = 3) -> List[PageInfo]:
        """Arama yap ve sonuç sayfalarını getir"""
        results = self.search(query, max_results=max_pages)
        
        pages = []
        for result in results:
            url = result.get("url")
            if url:
                page = self.fetch_page(url)
                if not page.error:
                    pages.append(page)
        
        return pages
    
    def summarize_page(self, url: str, max_length: int = 500) -> str:
        """Bir sayfayı özetle"""
        page = self.fetch_page(url)
        
        if page.error:
            return f"Sayfa yüklenemedi: {page.error}"
        
        # İlk paragrafları al
        paragraphs = [p.strip() for p in page.text.split('\n') if p.strip() and len(p.strip()) > 50]
        
        summary = f"Başlık: {page.title}\n"
        summary += f"Kaynak: {page.url}\n"
        summary += f"Kelimeler: ~{page.word_count}\n"
        summary += f"Bağlantılar: {len(page.links)} ({sum(1 for l in page.links if l.is_internal)} dahili)\n\n"
        
        if paragraphs:
            content = "\n".join(paragraphs[:5])
            if len(content) > max_length:
                content = content[:max_length] + "..."
            summary += content
        
        return summary
    
    def open_in_browser(self, url: str) -> bool:
        """Sayfayı varsayılan tarayıcıda aç"""
        if not WEBBROWSER_OK:
            return False
        
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
            return True
        except Exception as e:
            logger.warning(f"Tarayıcı açma hatası: {e}")
            return False
    
    def _rate_limit(self):
        """Rate limiting - istekler arasında bekle"""
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()
    
    def _add_to_history(self, url: str, page: PageInfo):
        """Ziyaret geçmişine ekle"""
        self.visit_history.append({
            "url": url,
            "status": page.status_code,
            "error": page.error,
            "load_time": page.load_time,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.visit_history) > self.max_history:
            self.visit_history = self.visit_history[-self.max_history:]
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Ziyaret geçmişini getir"""
        return self.visit_history[-limit:]
    
    def clear_cache(self):
        """Önbelleği temizle"""
        self.cache.clear()
        logger.info("Web önbelleği temizlendi")
    
    def get_status(self) -> Dict:
        """Web Agent durumu"""
        return {
            "requests_available": REQUESTS_OK,
            "beautifulsoup_available": BS4_OK,
            "cache_size": len(self.cache),
            "visit_history": len(self.visit_history),
            "last_request": self._last_request
        }


# ─────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────

_web_agent_instance = None

def get_web_agent() -> WebAgent:
    """WebAgent singleton instance'ını al"""
    global _web_agent_instance
    if _web_agent_instance is None:
        _web_agent_instance = WebAgent()
    return _web_agent_instance


if __name__ == "__main__":
    agent = get_web_agent()
    
    # Test
    print("=" * 50)
    print("  Glassescat AI - Web Agent Test")
    print("=" * 50)
    
    print("\n1. DuckDuckGo arama:")
    results = agent.search("yapay zeka", max_results=3)
    for r in results[:3]:
        print(f"   • {r.get('title', '?')[:50]}")
        print(f"     {r.get('url', '?')}")
    
    print("\n2. Sayfa getir:")
    page = agent.fetch_page("https://example.com")
    print(f"   Başlık: {page.title}")
    print(f"   Durum: {page.status_code}")
    print(f"   Kelime: {page.word_count}")
    print(f"   Bağlantı: {len(page.links)}")
    
    print("\n3. Sayfa özeti:")
    summary = agent.summarize_page("https://example.com", max_length=200)
    print(f"   {summary[:200]}...")
    
    print("\nWeb Agent test tamamlandı!")
