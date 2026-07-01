import os
import re
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0'
]


class WebScraper:
    def __init__(self, delay: float = 1.0, timeout: int = 15, max_retries: int = 2):
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """Configure session with headers and cookies"""
        import random
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def _download_page(self, url: str) -> Optional[str]:
        """Download HTML content with retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url, 
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # Handle encoding
                if response.encoding and response.encoding != 'utf-8':
                    response.encoding = 'utf-8'
                
                html = response.text
                
                # Skip extremely large pages
                if len(html) > 10 * 1024 * 1024:  # 10MB limit
                    logger.warning(f"Página muy grande ({len(html)} chars): {url}")
                    return None
                
                return html
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Intento {attempt + 1} fallido para {url}: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * (attempt + 1))
                continue
        
        return None

    def _extract_cedula_nombre(self, text: str) -> Optional[tuple]:
        """Extract cedula and name from text using regex patterns"""
        # Clean text
        text = text.strip()
        
        # Venezuelan cedula patterns
        cedula_patterns = [
            r'(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)',  # Venezuelan format
            r'(\d{8})',  # Simple 8 digits
            r'(\d{4,})\s*(?:-|–)?\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',  # 12345 - Name
        ]
        
        for pattern in cedula_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                if len(match.groups()) >= 2:
                    # Pattern with name
                    return match.group(1).replace('.', '').replace('-', '').strip(), match.group(2).strip()
                elif len(match.groups()) == 1:
                    # Just cedula, try to extract name from surrounding text
                    cedula = match.group(1).replace('.', '').replace('-', '').strip()
                    return cedula, ''
        
        return None

    def _extract_from_tables(self, html: str, base_url: str) -> List[Dict]:
        """Extract person data from HTML tables"""
        personas = []
        soup = BeautifulSoup(html, 'lxml')
        
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                    
                cell_texts = [cell.get_text(separator=' ', strip=True) for cell in cells]
                
                # Try different column arrangements
                for i in range(min(len(cells), 4)):
                    for j in range(len(cells)):
                        if i == j:
                            continue
                        cedula_nombre = self._extract_cedula_nombre(f"{cell_texts[i]} {cell_texts[j]}")
                        if cedula_nombre and cedula_nombre[1]:
                            personas.append({
                                'cedula': cedula_nombre[0],
                                'nombre_completo': cedula_nombre[1],
                                'url_fuente': base_url,
                                'metadatos': {'tipo': 'tabla', 'fila': i}
                            })
                            break
                    if personas:
                        break
        
        return personas

    def _extract_from_lists(self, html: str, base_url: str) -> List[Dict]:
        """Extract person data from HTML lists"""
        personas = []
        soup = BeautifulSoup(html, 'lxml')
        
        for list_tag in soup.find_all(['ul', 'ol']):
            items = list_tag.find_all('li', recursive=False)
            
            for item in items:
                item_text = item.get_text(separator=' ', strip=True)
                
                # Patterns for list items
                patterns = [
                    r'(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)\s*[-–]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',
                    r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\s*[-–]\s*(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)',
                    r'(\d{8})\s*[-–]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, item_text, re.IGNORECASE)
                    if match:
                        cedula = match.group(1).replace('.', '').replace('-', '').replace('–', '').strip()
                        nombre = match.group(2).strip()
                        personas.append({
                            'cedula': cedula,
                            'nombre_completo': nombre,
                            'url_fuente': base_url,
                            'metadatos': {'tipo': 'lista'}
                        })
                        break
        
        return personas

    def _extract_from_regex(self, html: str, base_url: str) -> List[Dict]:
        """Extract using regex patterns for common layouts"""
        personas = []
        
        # WordPress/blogger patterns
        patterns = [
            r'<h[23][^>]*>\s*(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)\s*[-–]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\s*</h[23]>',
            r'>\s*(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)\s*[-–]\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\s*<',
            r'cédula[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}(?:-\d)?)[,\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE | re.DOTALL)
            for match in matches:
                cedula = match.group(1).replace('.', '').replace('-', '').strip()
                nombre = match.group(2).strip()
                
                if len(cedula) >= 6 and len(nombre) >= 2:
                    personas.append({
                        'cedula': cedula,
                        'nombre_completo': nombre,
                        'url_fuente': base_url,
                        'metadatos': {'tipo': 'regex'}
                    })
        
        return personas

    def scrape_page(self, url: str, pattern_type: str = 'auto') -> List[Dict]:
        """Main scraping method"""
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError("URL inválida, debe comenzar con http:// o https://")
        
        html = self._download_page(url)
        if not html:
            return []
        
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        personas = []
        
        if pattern_type in ('auto', 'table'):
            personas.extend(self._extract_from_tables(html, base_url))
        
        if pattern_type in ('auto', 'list'):
            personas.extend(self._extract_from_lists(html, base_url))
        
        if pattern_type in ('auto', 'regex'):
            personas.extend(self._extract_from_regex(html, base_url))
        
        # Deduplicate by cedula + nombre
        seen = set()
        unique_personas = []
        for p in personas:
            key = f"{p['cedula']}|{p['nombre_completo']}"
            if key not in seen:
                seen.add(key)
                unique_personas.append(p)
        
        return unique_personas


# Convenience function for FastAPI
async def scrape_url(url: str, pattern_type: str = 'auto') -> List[Dict]:
    """Scrape a single URL and return personas"""
    scraper = WebScraper(delay=0.5, timeout=10)
    return scraper.scrape_page(url, pattern_type)