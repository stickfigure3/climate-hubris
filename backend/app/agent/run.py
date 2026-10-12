"""Agent run: collect sources, extract findings, verify, store."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import date, datetime, timezone

import httpx

from ..config import settings
from ..regions import REGIONS, current_season
from ..store import Store, utcnow_iso
from . import extract as extraction
from .sources import SOURCES, collect

log = logging.getLogger(__name__)

FEED_IDS = {s.id for s in SOURCES if s.kind == "rss"} | {"reliefweb"}
SEEN_TTL_DAYS = 120
FINDING_TTL_DAYS = 3 * 365


def should_run(today: date) -> bool:
    """The trigger fires weekly. Run every week while any monsoon is active,
    otherwise only in the first and third weeks of the month (twice a month)."""
    if any(current_season(r, today) for r in REGIONS.values()):
        return True
    return today.day <= 7 or 15 <= today.day <= 21


def run(store: Store, today: date | None = None, force: bool = False, chain=None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    if not force and not should_run(today):
        log.info("agent skipped: off-season week")
        return {"status": "skipped"}

    client = httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=45, follow_redirects=True)
    documents, source_status = collect(client, today)

    seen = {item["sk"] for item in store.query("SEEN")}
    fresh = [d for d in documents if d.fingerprint not in seen]
    # Curated pages first (they change rarely and carry the most signal), then newest feed items.
    fresh.sort(key=lambda d: (d.source_id in FEED_IDS, -(d.published or date.min).toordinal()))
    batch, deferred = fresh[: settings.agent_max_documents], len(fresh) - settings.agent_max_documents

    model_name = None
    if batch and chain is None:
        chain, model_name = extraction.build_chain()

    now = int(time.time())
    stored = rejected = errors = 0
    for doc in batch:
        try:
            findings, dropped = extraction.extract(chain, doc)
        except Exception as exc:
            log.warning("extraction failed for %s: %s", doc.url, exc)
            errors += 1
            continue
        rejected += dropped
        for f in findings:
            finding_date = f.document_date or (doc.published or today).isoformat()
            digest = hashlib.sha256(f"{doc.url}|{f.evidence_quote}".encode()).hexdigest()[:12]
            store.put(
                f"FINDING#{f.region}",
                f"{finding_date}#{digest}",
                region=f.region,
                subregion=f.subregion,
                category=f.category,
                kind=f.kind,
                severity=f.severity,
                date=finding_date,
                date_basis="document" if f.document_date else ("published" if doc.published else "retrieved"),
                summary=f.summary,
                evidence_quote=f.evidence_quote,
                source_url=doc.url,
                source_org=doc.org,
                source_title=doc.title,
                extracted_at=utcnow_iso(),
                model=model_name or "injected",
                ttl=now + FINDING_TTL_DAYS * 86400,
            )
            stored += 1
        store.put("SEEN", doc.fingerprint, url=doc.url, seen_at=utcnow_iso(), ttl=now + SEEN_TTL_DAYS * 86400)

    summary = {
        "status": "ok" if errors == 0 else "partial",
        "documents_fetched": len(documents),
        "documents_new": len(fresh),
        "documents_processed": len(batch) - errors,
        "documents_deferred": max(deferred, 0),
        "findings_stored": stored,
        "findings_rejected_unverified": rejected,
        "extraction_errors": errors,
        "sources": source_status,
    }
    store.put_meta(
        "agent",
        source="LLM extraction over FAO GIEWS, FEWS NET, UN News, FloodList, NASA EO, GDACS",
        latest_data=today.isoformat(),
        model=model_name,
        **{k: v for k, v in summary.items() if k != "status"},
        status=summary["status"],
    )
    log.info("agent run: %s", {k: v for k, v in summary.items() if k != "sources"})
    return summary
