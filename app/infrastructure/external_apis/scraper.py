"""
Scraper partagé pour Google Search et Facebook public.
Utilise httpx + BeautifulSoup pour extraire les résultats.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus, unquote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Modèles de données ────────────────────────────────────────────────

@dataclass
class ScrapedResult:
    """Un résultat de recherche scrappé."""
    title: str
    url: str
    snippet: str
    source: str  # "google" | "facebook"
    image_url: str | None = None


@dataclass
class ScrapedArticle:
    """Contenu complet d'une page scrappée."""
    url: str
    title: str
    content: str
    author: str | None = None
    published_date: str | None = None
    image_url: str | None = None
    source: str = "web"


# ── Headers communs ───────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_LITE_HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


# ── DuckDuckGo Search Scraper (Lite) ──────────────────────────────────

async def search_duckduckgo(
    query: str,
    num_results: int = 10,
    site_filter: str | None = None,
) -> list[ScrapedResult]:
    """
    Recherche DuckDuckGo via l'interface Lite (rapide, sans JavaScript ni blocage).
    """
    full_query = f"site:{site_filter} {query}" if site_filter else query
    results: list[ScrapedResult] = []

    try:
        async with httpx.AsyncClient(
            headers=_LITE_HEADERS,
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": full_query},
            )
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                links = soup.select("a.result-link")
                snippets = soup.select("td.result-snippet")

                for link_el, snippet_el in zip(links, snippets):
                    href = link_el.get("href", "")
                    if not href.startswith("http"):
                        continue

                    title = link_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    source = "facebook" if "facebook.com" in href else "google"

                    results.append(
                        ScrapedResult(
                            title=title,
                            url=href,
                            snippet=snippet,
                            source=source,
                        )
                    )

                    if len(results) >= num_results:
                        break

    except Exception as exc:
        logger.warning("DuckDuckGo search failed for query=%r: %s", full_query, exc)

    return results


# ── Google Search Scraper ─────────────────────────────────────────────

async def search_google(
    query: str,
    num_results: int = 10,
    language: str = "fr",
    site_filter: str | None = None,
) -> list[ScrapedResult]:
    """
    Recherche Web (Google avec fallback transparent sur DDG Lite).
    """
    # DuckDuckGo Lite sert de moteur web principal ultra-rapide et fiable
    results = await search_duckduckgo(
        query=query,
        num_results=num_results,
        site_filter=site_filter,
    )
    if results:
        return results

    # Fallback Google si DDG n'a pas répondu
    raw_query = f"site:{site_filter} {query}" if site_filter else query
    url = (
        f"https://www.google.com/search"
        f"?q={quote_plus(raw_query)}"
        f"&num={num_results}"
        f"&hl={language}"
    )

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=5.0,
        ) as client:
            response = await client.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                for div in soup.select("div.g, div[data-sokoban-container]"):
                    link_el = div.select_one("a[href]")
                    title_el = div.select_one("h3")
                    snippet_el = (
                        div.select_one("div[data-sncf], span.st, div.VwiC3b")
                        or div.select_one("div[style*='line-clamp']")
                        or div.select_one("span")
                    )

                    if not link_el or not title_el:
                        continue

                    href = link_el.get("href", "")
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]

                    if not href.startswith("http"):
                        continue

                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    source = "facebook" if "facebook.com" in href else "google"

                    results.append(
                        ScrapedResult(
                            title=title,
                            url=href,
                            snippet=snippet,
                            source=source,
                        )
                    )

                    if len(results) >= num_results:
                        break

    except Exception as exc:
        logger.warning("Google search failed for query=%r: %s", raw_query, exc)

    return results


# ── Facebook Public Page Scraper ──────────────────────────────────────

async def search_facebook(
    query: str,
    num_results: int = 10,
) -> list[ScrapedResult]:
    """
    Recherche des publications et pages Facebook publiques
    via DuckDuckGo avec le filtre site:facebook.com.
    """
    fb_results = await search_duckduckgo(
        query=query,
        num_results=num_results,
        site_filter="facebook.com",
    )
    # Marquer explicitement comme source facebook
    for r in fb_results:
        r.source = "facebook"
    return fb_results


# ── Page Content Scraper ─────────────────────────────────────────────

async def scrape_page_content(url: str) -> ScrapedArticle | None:
    """
    Télécharge et extrait le contenu principal d'une page web.
    """
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Supprimer script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Titre
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # Image
        image_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

        # Auteur
        author = None
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"]

        # Date de publication
        published_date = None
        for attr in ["article:published_time", "datePublished", "date"]:
            date_meta = soup.find("meta", property=attr) or soup.find(
                "meta", attrs={"name": attr}
            )
            if date_meta and date_meta.get("content"):
                published_date = date_meta["content"]
                break

        # Contenu principal
        article_el = soup.find("article") or soup.find(
            "div", class_=re.compile(r"(content|article|post|entry)", re.I)
        )
        if article_el:
            content = article_el.get_text(separator="\n", strip=True)
        else:
            # Fallback : tous les paragraphes
            paragraphs = soup.find_all("p")
            content = "\n".join(
                p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30
            )

        if not content:
            content = soup.get_text(separator="\n", strip=True)[:3000]

        # Limiter la taille du contenu
        content = content[:5000]

        source = "facebook" if "facebook.com" in url else "web"

        return ScrapedArticle(
            url=url,
            title=title,
            content=content,
            author=author,
            published_date=published_date,
            image_url=image_url,
            source=source,
        )

    except Exception as exc:
        logger.warning("Failed to scrape page %s: %s", url, exc)
        return None


# ── Recherche combinée pour vérification ──────────────────────────────

async def search_and_verify(
    claim: str,
    num_results: int = 8,
) -> list[ScrapedResult]:
    """
    Effectue une recherche combinée Google (Web) + Facebook pour
    collecter des sources liées à une affirmation.
    """
    google_results = await search_google(claim, num_results=num_results)

    # Pour Facebook, extraire les mots-clés principaux pour un meilleur rappel
    words = [
        w
        for w in re.findall(r"\b\w{4,}\b", claim)
        if w.lower()
        not in {
            "dans", "pour", "avec", "cette", "sont", "leur", "plus",
            "tout", "tous", "fait", "mais", "comme", "aussi", "bien",
            "cette", "ceux", "celles", "vont", "avoir", "etre", "était",
        }
    ]
    fb_query = " ".join(words[:5]) if words else claim
    facebook_results = await search_facebook(fb_query, num_results=max(3, num_results // 2))

    # Dédupliquer par URL
    seen_urls: set[str] = set()
    combined: list[ScrapedResult] = []

    for result in google_results + facebook_results:
        normalized = result.url.rstrip("/").lower()
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            combined.append(result)

    return combined
