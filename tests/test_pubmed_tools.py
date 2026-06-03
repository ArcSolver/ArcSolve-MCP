"""PubMed 도구 런타임 검증 — 네트워크 없이 요청 조립·응답 파싱·에러 매핑·키 유무 확인.

esearch/esummary는 get_json(dict 반환), efetch는 get_text(raw XML str 반환)를 쓴다.
키·tool·email은 쿼리 파라미터로 들어가는지(헤더 아님) 확인한다(키 없으면 api_key 없음).
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.pubmed.tools import register

MOD = "arcsolve.services.pubmed.tools"

ESEARCH_BODY = {
    "esearchresult": {
        "count": "67815",
        "retmax": "2",
        "retstart": "0",
        "idlist": ["42233250", "42232503"],
    }
}

ESUMMARY_BODY = {
    "result": {
        "uids": ["31452104"],
        "31452104": {
            "uid": "31452104",
            "title": "Molegro Virtual Docker for Docking.",
            "authors": [
                {"name": "Bitencourt-Ferreira G", "authtype": "Author"},
                {"name": "de Azevedo WF", "authtype": "Author"},
            ],
            "source": "Methods Mol Biol",
            "fulljournalname": "Methods in molecular biology (Clifton, N.J.)",
            "pubdate": "2019",
            "volume": "2053",
            "pages": "149-167",
            "articleids": [
                {"idtype": "doi", "value": "10.1007/978-1-4939-9752-7_10"},
            ],
        },
    }
}

EFETCH_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID Version="1">31452104</PMID>
<Article><Journal><Title>Methods Mol Biol</Title></Journal>
<ArticleTitle>Molegro Virtual Docker for Docking.</ArticleTitle>
<Abstract><AbstractText>A docking program.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


@pytest.fixture
def tools(monkeypatch, load_tools):
    """키 없는 기본 환경(초당 3건 한도). NCBI_* env 제거."""
    for var in ("NCBI_API_KEY", "NCBI_EMAIL", "NCBI_TOOL"):
        monkeypatch.delenv(var, raising=False)
    return load_tools(register)


# ─── pubmed_search (get_json) ───────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESEARCH_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["pubmed_search"](query="crispr AND cas9[ti]", retmax=2)
    assert http.last["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    assert http.last["params"]["db"] == "pubmed"
    assert http.last["params"]["term"] == "crispr AND cas9[ti]"
    assert http.last["params"]["retmode"] == "json"  # esearch는 JSON
    assert http.last["params"]["retmax"] == 2
    # 키 없음 → api_key 파라미터 없음. tool 기본값은 붙는다(식별 권장).
    assert "api_key" not in http.last["params"]
    assert http.last["params"]["tool"] == "ArcSolve-MCP"
    assert "총 67815건" in out
    assert "42233250, 42232503" in out


async def test_search_sort_param(tools, monkeypatch, recording_http):
    http = recording_http(ret={"esearchresult": {"count": "0", "idlist": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_search"](query="x", sort="pub_date")
    assert http.last["params"]["sort"] == "pub_date"
    assert "검색 결과 없음" in out and "총 0건" in out


async def test_search_bad_retmax_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESEARCH_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_search"](query="x", retmax=10001)
    assert "retmax" in out and "10000" in out
    assert not http.calls  # 계약 위반은 HTTP 전에 막힘


async def test_search_bad_sort_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESEARCH_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_search"](query="x", sort="newest")
    assert "sort" in out
    assert not http.calls


async def test_search_maps_upstream_error_in_body(tools, monkeypatch, recording_http):
    http = recording_http(ret={"esearchresult": {"ERROR": "Invalid field tag", "idlist": []}})
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_search"](query="x[badtag]")
    assert "검색 오류" in out and "Invalid field tag" in out


# ─── api_key/tool/email는 쿼리 파라미터(헤더 아님) ─────────


async def test_api_key_and_email_go_into_query_params(monkeypatch, load_tools, recording_http):
    monkeypatch.setenv("NCBI_API_KEY", "SECRET")
    monkeypatch.setenv("NCBI_EMAIL", "dev@example.com")
    monkeypatch.delenv("NCBI_TOOL", raising=False)
    tools = load_tools(register)
    http = recording_http(ret={"esearchresult": {"count": "1", "idlist": ["1"]}})
    monkeypatch.setattr(f"{MOD}.get_json", http)

    await tools["pubmed_search"](query="x")
    # 쿼리 파라미터로 들어가야 한다(헤더 아님).
    assert http.last["params"]["api_key"] == "SECRET"
    assert http.last["params"]["email"] == "dev@example.com"
    assert http.last.get("headers") is None


# ─── pubmed_get_summary (get_json) ──────────────────────────


async def test_get_summary_single_detail(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESUMMARY_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)

    out = await tools["pubmed_get_summary"](ids="31452104")
    assert http.last["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    assert http.last["params"]["id"] == "31452104"
    assert http.last["params"]["retmode"] == "json"
    assert "31452104" in out
    assert "Molegro Virtual Docker" in out
    assert "Bitencourt-Ferreira G 외 1명" in out
    assert "Methods in molecular biology" in out  # fulljournalname
    assert "2053" in out  # volume
    assert "10.1007/978-1-4939-9752-7_10" in out  # DOI from articleids


async def test_get_summary_multiple_list(tools, monkeypatch, recording_http):
    body = {
        "result": {
            "uids": ["1", "2"],
            "1": {"uid": "1", "title": "First", "pubdate": "2020", "source": "J1",
                  "authors": [{"name": "A One"}]},
            "2": {"uid": "2", "title": "Second", "pubdate": "2021", "source": "J2",
                  "authors": [{"name": "B Two"}]},
        }
    }
    http = recording_http(ret=body)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_get_summary"](ids="1,2")
    assert "총 2건" in out
    assert "First" in out and "Second" in out
    assert "[1]" in out and "[2]" in out


async def test_get_summary_empty_ids_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESUMMARY_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_get_summary"](ids="   ")
    assert "비어" in out
    assert not http.calls


async def test_get_summary_too_many_ids_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=ESUMMARY_BODY)
    monkeypatch.setattr(f"{MOD}.get_json", http)
    many = ",".join(str(i) for i in range(201))
    out = await tools["pubmed_get_summary"](ids=many)
    assert "200" in out
    assert not http.calls


# ─── pubmed_fetch_abstract (get_text + XML) ─────────────────


async def test_fetch_abstract_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=EFETCH_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["pubmed_fetch_abstract"](ids="31452104")
    assert http.last["url"] == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    # efetch는 XML — rettype=abstract & retmode=xml.
    assert http.last["params"]["rettype"] == "abstract"
    assert http.last["params"]["retmode"] == "xml"
    assert "31452104" in out
    assert "Molegro Virtual Docker for Docking." in out
    assert "A docking program." in out


async def test_fetch_abstract_structured_labels(tools, monkeypatch, recording_http):
    xml = """<?xml version="1.0" ?>
    <PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>
    <Article><ArticleTitle>T</ArticleTitle><Abstract>
    <AbstractText Label="BACKGROUND">bg</AbstractText>
    <AbstractText Label="RESULTS">res</AbstractText>
    </Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    http = recording_http(ret=xml)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["pubmed_fetch_abstract"](ids="1")
    assert "BACKGROUND: bg" in out and "RESULTS: res" in out


async def test_fetch_abstract_missing_abstract(tools, monkeypatch, recording_http):
    xml = """<?xml version="1.0" ?>
    <PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>9</PMID>
    <Article><ArticleTitle>No abs</ArticleTitle></Article>
    </MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    http = recording_http(ret=xml)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["pubmed_fetch_abstract"](ids="9")
    assert "(초록 없음)" in out


async def test_fetch_abstract_empty_set(tools, monkeypatch, recording_http):
    http = recording_http(ret='<?xml version="1.0" ?><PubmedArticleSet></PubmedArticleSet>')
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["pubmed_fetch_abstract"](ids="999999999")
    assert "결과 없음" in out


async def test_fetch_abstract_parse_error(tools, monkeypatch, recording_http):
    http = recording_http(ret="<PubmedArticleSet><PubmedArticle>broken")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["pubmed_fetch_abstract"](ids="1")
    assert "파싱 실패" in out


# ─── HTTP 에러 매핑 ─────────────────────────────────────────


async def test_search_maps_429_suggests_key(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(429, "too many requests"))
    monkeypatch.setattr(f"{MOD}.get_json", http)
    out = await tools["pubmed_search"](query="x")
    assert "429" in out and "한도" in out
    assert "NCBI_API_KEY" in out  # 키 권장 안내


async def test_fetch_maps_400(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(400, "bad request"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["pubmed_fetch_abstract"](ids="1")
    assert "400" in out
