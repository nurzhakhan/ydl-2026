"""Скрейпер сайта фонда.

Идём по sitemap.xml, скачиваем страницы, чистим HTML (убираем меню/скрипты),
определяем язык по URL (/ru/ /kk/ /en/) и сохраняем тексты в
data/knowledge/site_docs.jsonl — по одному документу на строку.

Запуск отдельно:  python -m src.data_collection.scrape_site
Обычно вызывается из ingest.py.
"""
import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.config import settings, KNOWLEDGE_DIR

SITE_DOCS_PATH = KNOWLEDGE_DIR / "site_docs.jsonl"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; YessenovFAQBot/1.0; +knowledge-base)"
}


def _detect_lang(url: str) -> str:
    """Язык страницы по префиксу пути. По умолчанию русский."""
    path = urlparse(url).path
    if "/en/" in path:
        return "en"
    if "/kk/" in path or "/kz/" in path:
        return "kk"
    return "ru"


def _section(url: str) -> str:
    """Первый значимый сегмент пути (без языкового префикса). '' = главная."""
    segs = [s for s in urlparse(url).path.strip("/").split("/") if s]
    if segs and segs[0] in ("ru", "en", "kk", "kz"):
        segs = segs[1:]
    return segs[0] if segs else ""


def _is_allowed(url: str) -> bool:
    """True, если страница в разрешённых разделах и не в списке исключений."""
    path = urlparse(url).path
    if any(excl in path for excl in settings.site_exclude_paths):
        return False
    return _section(url) in settings.site_include_sections


def get_sitemap_urls(client: httpx.Client) -> list[str]:
    """Собирает все URL из sitemap.xml (с учётом sitemap-индекса)."""
    base = settings.site_base_url.rstrip("/")
    urls: list[str] = []
    try:
        resp = client.get(f"{base}/sitemap.xml", timeout=settings.scrape_timeout)
        resp.raise_for_status()
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", resp.text)
        for loc in locs:
            if loc.endswith(".xml"):  # вложенный sitemap
                try:
                    sub = client.get(loc, timeout=settings.scrape_timeout)
                    urls.extend(re.findall(r"<loc>\s*(.*?)\s*</loc>", sub.text))
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! не удалось прочитать вложенный sitemap {loc}: {exc}")
            else:
                urls.append(loc)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! sitemap недоступен ({exc}), пробуем только главную")
        urls.append(base + "/")

    # Уникальные, с сохранением порядка
    return list(dict.fromkeys(u for u in urls if u.startswith("http")))


def extract_text(html: str) -> tuple[str, str]:
    """Возвращает (заголовок, основной текст) из HTML, без меню и скриптов."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "noscript", "form", "svg", "aside"]
    ):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    container = soup.find("main") or soup.find("article") or soup.body or soup
    text = container.get_text(separator="\n")
    # Чистим пустые строки
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return title, text


def scrape() -> int:
    """Скачивает страницы и пишет в site_docs.jsonl. Возвращает число документов."""
    written = 0
    with httpx.Client(headers=_HEADERS, follow_redirects=True) as client:
        all_urls = get_sitemap_urls(client)
        urls = [u for u in all_urls if _is_allowed(u)]
        skipped = len(all_urls) - len(urls)
        print(
            f"Найдено URL: {len(all_urls)} | разрешено разделами "
            f"{settings.site_include_sections}: {len(urls)} | "
            f"исключено (новости и пр.): {skipped}"
        )
        urls = urls[: settings.scrape_max_pages]

        with open(SITE_DOCS_PATH, "w", encoding="utf-8") as out:
            for url in tqdm(urls, desc="Скрейпинг", unit="стр"):
                try:
                    resp = client.get(url, timeout=settings.scrape_timeout)
                    if resp.status_code != 200 or "text/html" not in resp.headers.get(
                        "content-type", ""
                    ):
                        continue
                    title, text = extract_text(resp.text)
                    if len(text) < 200:  # пропускаем почти пустые страницы
                        continue
                    doc = {
                        "source": url,
                        "title": title,
                        "lang": _detect_lang(url),
                        "text": text,
                        "origin": "site",
                    }
                    out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                    written += 1
                except Exception as exc:  # noqa: BLE001
                    tqdm.write(f"  ! {url}: {exc}")

    print(f"Готово. Сохранено документов: {written} -> {SITE_DOCS_PATH}")
    return written


if __name__ == "__main__":
    scrape()
