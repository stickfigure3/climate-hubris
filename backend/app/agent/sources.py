"""Curated sources the agent reads, and how each is turned into plain-text documents."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from time import mktime

import feedparser
import httpx
from bs4 import BeautifulSoup

from ..config import settings

log = logging.getLogger(__name__)

# Documents longer than this are cut, and the cut is logged. The quote check in
# extract.py runs against the same cut text the model saw.
MAX_CHARS = 20_000
RSS_MAX_AGE_DAYS = 21

KEYWORDS = re.compile(
    r"monsoon|rainfall|rainy season|rains\b|drought|dry spell|flood|precipitation|wet season",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Source:
    id: str
    org: str
    url: str
    kind: str  # "page" | "rss"
    region_hint: str | None = None
    country: str | None = None  # ISO3, for sources about a single country


def _giews(code: str, region: str) -> Source:
    return Source(
        f"giews-{code.lower()}",
        "FAO GIEWS",
        f"https://www.fao.org/giews/countrybrief/country.jsp?code={code}",
        "page",
        region,
        code,
    )


SOURCES: list[Source] = [
    # FAO GIEWS country briefs: rainfall and crop conditions, updated a few times a year.
    # One for every country that is, or contains, a subregion (Japan's has not been updated since 2016).
    *[_giews(c, "south_asia") for c in ("IND", "PAK", "BGD", "NPL", "LKA")],
    *[_giews(c, "east_asia") for c in ("CHN", "VNM", "KOR", "PRK")],
    *[_giews(c, "west_africa") for c in ("NER", "MLI", "BFA", "NGA", "GHA", "CIV", "SEN", "GIN", "SLE", "BEN", "TGO", "TCD")],
    *[_giews(c, "southern_africa") for c in ("ZWE", "MOZ", "ZMB", "MWI", "ZAF", "TZA", "MDG", "AGO")],
    *[_giews(c, "south_america") for c in ("BRA", "BOL", "PRY")],
    # FEWS NET regional overviews.
    Source("fewsnet-west-africa", "FEWS NET", "https://fews.net/west-africa", "page", "west_africa"),
    Source("fewsnet-southern-africa", "FEWS NET", "https://fews.net/southern-africa", "page", "southern_africa"),
    # Feeds, filtered to recent items that mention rainfall, drought or flooding.
    Source("un-news-climate", "UN News", "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml", "rss"),
    Source("floodlist", "FloodList", "https://floodlist.com/feed", "rss"),
    Source("nasa-eo-hazards", "NASA Earth Observatory", "https://earthobservatory.nasa.gov/feeds/natural-hazards.rss", "rss"),
    Source("gdacs", "GDACS", "https://www.gdacs.org/xml/rss.xml", "rss"),
]

# FAO GIEWS briefs print their own date, e.g. "Reference Date: 13-February-2026".
REFERENCE_DATE = re.compile(r"Reference Date:\s*(\d{1,2}-[A-Za-z]+-\d{4})")

RELIEFWEB_API = "https://api.reliefweb.int/v2/reports"


@dataclass(frozen=True)
class Document:
    source_id: str
    org: str
    url: str
    title: str
    text: str
    region_hint: str | None
    published: date | None  # None when the page prints no date of its own
    country: str | None = None

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(f"{self.url}\n{self.text}".encode()).hexdigest()[:32]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _cut(text: str, url: str) -> str:
    if len(text) > MAX_CHARS:
        log.warning("truncating %s from %d to %d chars", url, len(text), MAX_CHARS)
        return text[:MAX_CHARS]
    return text


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Not <form> or <header>: some sites (FAO GIEWS) wrap the whole article in one.
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    return _clean(soup.get_text(" "))


def _page(client: httpx.Client, source: Source) -> list[Document]:
    response = client.get(source.url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = _clean(soup.title.get_text()) if soup.title else source.id
    text = _cut(html_to_text(response.text), source.url)
    published = None
    if match := REFERENCE_DATE.search(text):
        try:
            published = datetime.strptime(match.group(1), "%d-%B-%Y").date()
        except ValueError:
            pass
    return [Document(source.id, source.org, source.url, title, text, source.region_hint, published, source.country)]


def _rss(client: httpx.Client, source: Source, today: date) -> list[Document]:
    response = client.get(source.url)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    cutoff = today - timedelta(days=RSS_MAX_AGE_DAYS)
    docs = []
    for entry in feed.entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime.fromtimestamp(mktime(stamp), timezone.utc).date() if stamp else None
        if published is None or published < cutoff:
            continue
        body = " ".join(c.get("value", "") for c in entry.get("content", [])) or entry.get("summary", "")
        title = _clean(entry.get("title", ""))
        text = _cut(_clean(f"{title}. {html_to_text(body)}"), entry.get("link", source.url))
        if not KEYWORDS.search(text):
            continue
        docs.append(
            Document(source.id, source.org, entry.get("link", source.url), title, text, source.region_hint, published)
        )
    return docs


def _reliefweb(client: httpx.Client, today: date) -> list[Document]:
    since = (today - timedelta(days=RSS_MAX_AGE_DAYS)).isoformat()
    payload = {
        "appname": settings.reliefweb_appname,
        "limit": 15,
        "sort": ["date.created:desc"],
        "query": {"value": "monsoon OR \"rainy season\" OR drought", "operator": "OR"},
        "filter": {"field": "date.created", "value": {"from": f"{since}T00:00:00+00:00"}},
        "fields": {"include": ["title", "body", "url", "date.created"]},
    }
    response = client.post(RELIEFWEB_API, params={"appname": settings.reliefweb_appname}, json=payload)
    response.raise_for_status()
    docs = []
    for item in response.json().get("data", []):
        fields = item["fields"]
        text = _cut(_clean(f"{fields['title']}. {fields.get('body', '')}"), fields["url"])
        published = date.fromisoformat(fields["date"]["created"][:10])
        docs.append(Document("reliefweb", "ReliefWeb", fields["url"], fields["title"], text, None, published))
    return docs


def collect(client: httpx.Client, today: date) -> tuple[list[Document], dict[str, str]]:
    """Fetch every source. Returns the documents and a per-source status map."""
    documents: list[Document] = []
    status: dict[str, str] = {}
    for source in SOURCES:
        try:
            docs = _page(client, source) if source.kind == "page" else _rss(client, source, today)
            documents.extend(docs)
            status[source.id] = f"ok ({len(docs)})"
        except Exception as exc:  # one broken source must not stop the run
            log.warning("source %s failed: %s", source.id, exc)
            status[source.id] = f"error: {exc.__class__.__name__}"
    if settings.reliefweb_appname:
        try:
            docs = _reliefweb(client, today)
            documents.extend(docs)
            status["reliefweb"] = f"ok ({len(docs)})"
        except Exception as exc:
            log.warning("source reliefweb failed: %s", exc)
            status["reliefweb"] = f"error: {exc.__class__.__name__}"
    else:
        status["reliefweb"] = "skipped: no approved appname configured"
    return documents, status
