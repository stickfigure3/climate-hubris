from datetime import date

from app.agent import extract
from app.agent import run as agent_run
from app.agent.extract import Extraction, Finding, quote_is_verbatim
from app.agent.sources import Document, html_to_text

TEXT = (
    "Reference Date: 02-September-2026. Seasonal rains were well below average across the "
    "northwest, where cumulative rainfall since June was 30 percent below the long-term mean."
)


def _doc(**overrides) -> Document:
    base = dict(source_id="giews-ind", org="FAO GIEWS", url="https://example.org/brief", title="Brief",
                text=TEXT, region_hint="south_asia", published=None)
    return Document(**{**base, **overrides})


def _finding(quote: str, **overrides) -> Finding:
    base = dict(region="south_asia", category="below_average_rainfall", kind="observed", severity=6,
                summary="Rainfall in the northwest was 30 percent below the long-term mean.",
                evidence_quote=quote)
    return Finding(**{**base, **overrides})


class FakeChain:
    def __init__(self, findings):
        self.findings = findings

    def invoke(self, _inputs):
        return Extraction(findings=self.findings)


def test_quote_check_tolerates_case_and_whitespace_only():
    assert quote_is_verbatim("seasonal rains were   WELL below average across the northwest", TEXT)
    assert not quote_is_verbatim("Seasonal rains failed completely across the northwest", TEXT)
    assert not quote_is_verbatim("below average", TEXT)  # too short to count as evidence


def test_findings_without_a_verbatim_quote_are_dropped():
    real = _finding("cumulative rainfall since June was 30 percent below the long-term mean")
    invented = _finding("The monsoon collapsed and millions face famine in the northwest region")
    kept, rejected = extract.extract(FakeChain([real, invented]), _doc())
    assert kept == [real]
    assert rejected == 1


def test_findings_whose_evidence_is_off_topic_are_dropped():
    text = TEXT + " Wheat output is forecast to remain below average as rising costs discourage planting."
    off_topic = _finding("Wheat output is forecast to remain below average as rising costs discourage planting")
    kept, rejected = extract.extract(FakeChain([off_topic]), _doc(text=text))
    assert kept == [] and rejected == 1


def test_a_date_the_document_does_not_print_is_discarded():
    quote = "Seasonal rains were well below average across the northwest"
    kept, _ = extract.extract(FakeChain([_finding(quote, document_date="2026-09-02")]), _doc())
    assert kept[0].document_date == "2026-09-02"
    kept, _ = extract.extract(FakeChain([_finding(quote, document_date="2019-01-01")]), _doc())
    assert kept[0].document_date is None


def test_html_to_text_drops_scripts_and_navigation():
    html = "<html><nav>Menu</nav><script>x()</script><p>Rains  were\npoor.</p><footer>F</footer></html>"
    assert html_to_text(html) == "Rains were poor."


def test_run_stores_findings_once(store, monkeypatch):
    doc = _doc(published=date(2026, 9, 2))
    monkeypatch.setattr(agent_run, "collect", lambda client, today: ([doc], {"giews-ind": "ok (1)"}))
    chain = FakeChain([_finding("Seasonal rains were well below average across the northwest")])

    first = agent_run.run(store, today=date(2026, 9, 7), chain=chain)
    assert first["findings_stored"] == 1
    stored = store.query("FINDING#south_asia")
    assert stored[0]["source_url"] == "https://example.org/brief"
    assert stored[0]["date"] == "2026-09-02"  # the feed item's publication date

    second = agent_run.run(store, today=date(2026, 9, 14), chain=chain)
    assert second["documents_new"] == 0  # unchanged document is not sent to the model again
    assert len(store.query("FINDING#south_asia")) == 1
    assert store.get_meta()["agent"]["status"] == "ok"
