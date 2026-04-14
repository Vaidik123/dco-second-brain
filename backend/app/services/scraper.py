import trafilatura
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def scrape_url(url: str) -> dict:
    """Fetch and extract clean text from any URL."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return _fallback_scrape(url)

        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
        metadata = trafilatura.extract_metadata(downloaded)

        title = metadata.title if metadata else None
        author = metadata.author if metadata else None
        date = metadata.date if metadata else None

        if not text:
            return _fallback_scrape(url)

        return {
            "title": title,
            "content": text,
            "author": author,
            "published_at": date,
            "url": url,
        }
    except Exception as e:
        return {"title": None, "content": "", "author": None, "published_at": None, "url": url, "error": str(e)}


def _fallback_scrape(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else None
        return {"title": title, "content": text[:50000], "author": None, "published_at": None, "url": url}
    except Exception as e:
        return {"title": None, "content": "", "author": None, "published_at": None, "url": url, "error": str(e)}
