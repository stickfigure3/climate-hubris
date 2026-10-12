"""LLM extraction of monsoon statements, with a verbatim-quote check on every finding."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ..config import settings
from ..regions import REGIONS, SUBREGIONS, subregions_of
from .sources import KEYWORDS, Document

RegionId = Literal[
    "south_asia", "east_asia", "west_africa", "australia", "south_america", "southern_africa"
]
Category = Literal["monsoon_failure", "below_average_rainfall", "drought", "flooding", "near_normal"]

MIN_QUOTE_CHARS = 25


class Finding(BaseModel):
    region: RegionId = Field(description="The monsoon region the statement is about.")
    subregion: str | None = Field(
        default=None,
        description="The subregion id from the list, only if the quoted statement is about that country, "
        "state or province specifically. Leave empty for statements about the region or a whole "
        "multi-subregion country.",
    )
    category: Category
    kind: Literal["observed", "forecast"] = Field(
        description="observed = the text reports it has happened or is happening; forecast = the text expects it."
    )
    severity: int = Field(ge=0, le=10, description="0 = no stress, 10 = catastrophic failure or flooding.")
    summary: str = Field(description="One sentence, using only what the source states.")
    evidence_quote: str = Field(
        description="A sentence or clause copied character-for-character from the document that states this."
    )
    document_date: str | None = Field(
        default=None,
        description="ISO date (YYYY-MM-DD) the document gives for itself, only if printed in the text.",
    )


class Extraction(BaseModel):
    findings: list[Finding] = Field(default_factory=list)


SYSTEM = """You read humanitarian and meteorological bulletins and extract explicit statements about \
how a monsoon or rainy season is performing.

Report a finding only when the document itself states that rainfall was below average, that a monsoon \
or rainy season failed or was delayed, that there is drought, or that there is flooding from seasonal \
rains, in one of these regions:
{regions}

Rules:
- Use only what this document says. Do not add background knowledge, and do not infer conditions the \
text does not state.
- Every finding needs an evidence_quote copied exactly from the document. Findings whose quote is not \
found in the document are discarded automatically.
- Each region lists its subregions as id (name). Set subregion only when the evidence_quote itself is \
about that place; a statement about all of India, China or Brazil has no subregion.
- Skip statements about other regions and about events unrelated to seasonal rainfall (earthquakes, \
cyclones outside the monsoon, conflict).
- Set kind to "forecast" when the document predicts or expects the condition, and "observed" when it \
reports it as having happened or as under way. Never present a forecast as observed.
- If the document states that rainfall was near or above average with no harm, report it once with \
category near_normal and a severity of 0 to 2.
- Severity guide: 1-3 localized or minor deficits; 4-6 widespread below-average rains, crop stress or \
significant flooding; 7-8 severe drought, monsoon failure or major flood disaster; 9-10 catastrophic, \
national-scale failure.
- Most documents contain zero or one finding. Returning an empty list is the correct answer when \
nothing qualifies."""

HUMAN = """Source: {org}
Title: {title}
Expected region (a hint, may be wrong or absent): {region_hint}

Document:
<document>
{text}
</document>"""

PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM), ("human", HUMAN)])


def build_model():
    """The chat model for extraction. Bedrock authenticates with the Lambda role."""
    if settings.llm_provider == "openai":
        import boto3
        from langchain_openai import ChatOpenAI

        key = boto3.client("ssm", region_name=settings.aws_region).get_parameter(
            Name=settings.openai_key_param, WithDecryption=True
        )["Parameter"]["Value"]
        return ChatOpenAI(model=settings.openai_model, api_key=key, temperature=0), settings.openai_model

    from langchain_aws import ChatBedrockConverse

    model = ChatBedrockConverse(
        model=settings.bedrock_model, region_name=settings.aws_region, max_tokens=4096
    )
    return model, settings.bedrock_model


def build_chain():
    model, model_name = build_model()
    return PROMPT | model.with_structured_output(Extraction), model_name


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_is_verbatim(quote: str, text: str) -> bool:
    """True when the quote appears in the document, ignoring case, whitespace and quote style."""
    q = _normalize(quote).strip(" .\"'")
    return len(q) >= MIN_QUOTE_CHARS and q in _normalize(text)


def quote_is_on_topic(quote: str) -> bool:
    """The evidence itself has to mention rainfall, drought or flooding."""
    return bool(KEYWORDS.search(quote))


def _date_is_supported(iso: str | None, text: str) -> bool:
    """Accept a model-reported date only if it parses and its year is printed in the document."""
    if not iso or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        return False
    return iso[:4] in text


def region_list() -> str:
    """The regions and their subregions, as the prompt presents them."""
    lines = []
    for region in REGIONS.values():
        subregions = ", ".join(f"{s.id.split('.')[1]} ({s.name})" for s in subregions_of(region.id))
        lines.append(f"- {region.id}: {region.name} monsoon. Subregions: {subregions}")
    return "\n".join(lines)


def resolve_subregion(region: str, named: str | None, country: str | None) -> str | None:
    """The subregion id a finding belongs to, decided by code rather than trusted from the model.

    A name the model gives is kept only if it is one of the region's subregions. Otherwise a
    source about a single country counts towards the one subregion that is that country.
    """
    if named:
        candidate = named if "." in named else f"{region}.{named}"
        if candidate in SUBREGIONS and SUBREGIONS[candidate].region == region:
            return candidate
    if country:
        whole = [s.id for s in subregions_of(region) if s.parts.get(country) == ()]
        if len(whole) == 1:
            return whole[0]
    return None


def extract(chain, doc: Document) -> tuple[list[Finding], int]:
    """Run the model on one document. Returns (verified findings, number rejected)."""
    result: Extraction = chain.invoke(
        {
            "regions": region_list(),
            "org": doc.org,
            "title": doc.title,
            "region_hint": doc.region_hint or "none",
            "text": doc.text,
        }
    )
    kept, rejected = [], 0
    for finding in result.findings:
        if not quote_is_verbatim(finding.evidence_quote, doc.text) or not quote_is_on_topic(finding.evidence_quote):
            rejected += 1
            continue
        if not _date_is_supported(finding.document_date, doc.text):
            finding.document_date = None
        finding.subregion = resolve_subregion(finding.region, finding.subregion, doc.country)
        kept.append(finding)
    return kept, rejected
