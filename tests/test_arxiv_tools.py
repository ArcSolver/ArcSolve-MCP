"""arXiv 도구 런타임 검증 — 네트워크 없이 요청 조립·XML 응답 파싱·error-entry/에러 매핑.

get_text는 raw str(XML)을 돌려주므로 RecordingHTTP의 ret도 str(XML)로 준다.
무인증 — 자격증명 env가 없다(식별용 User-Agent만 확인).
"""

import pytest

from arcsolve.http import UpstreamError
from arcsolve.services.arxiv.tools import register

MOD = "arcsolve.services.arxiv.tools"

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>42</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>1</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/1605.08386v1</id>
    <title>Multimatricvariate distribution</title>
    <summary>An abstract here.</summary>
    <published>2016-05-26T17:59:02Z</published>
    <updated>2016-05-27T10:00:00Z</updated>
    <author><name>Jose A. Diaz-Garcia</name></author>
    <author><name>Ramon Gutierrez-Jaimez</name></author>
    <arxiv:comment>23 pages</arxiv:comment>
    <arxiv:journal_ref>J. Stat. 12 (2016)</arxiv:journal_ref>
    <arxiv:doi>10.1000/xyz123</arxiv:doi>
    <link href="http://arxiv.org/abs/1605.08386v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/1605.08386v1" rel="related"
          type="application/pdf"/>
    <category term="math.ST" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:primary_category term="math.ST" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>"""

EMPTY_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>0</opensearch:totalResults>
</feed>"""

ERROR_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_oops</id>
    <title>Error</title>
    <summary>incorrect id format for oops</summary>
  </entry>
</feed>"""

TWO_ENTRY_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1605.08386v1</id>
    <title>First</title>
    <published>2016-05-26T00:00:00Z</published>
    <author><name>A One</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/cond-mat/0207270v1</id>
    <title>Second</title>
    <published>2002-07-11T00:00:00Z</published>
    <author><name>B Two</name></author>
  </entry>
</feed>"""


@pytest.fixture
def tools(load_tools):
    return load_tools(register)


# ─── search ─────────────────────────────────────────────────


async def test_search_request_and_output(tools, monkeypatch, recording_http):
    http = recording_http(ret=FEED_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["arxiv_search"](query="ti:electron", max_results=5)
    assert http.last["url"] == "https://export.arxiv.org/api/query"
    assert http.last["params"]["search_query"] == "ti:electron"
    assert http.last["params"]["max_results"] == 5
    assert http.last["params"]["start"] == 0
    # 식별용 User-Agent(무인증)
    assert "ArcSolve-MCP" in http.last["headers"]["User-Agent"]
    assert "총 42건" in out
    assert "1605.08386v1" in out and "Multimatricvariate" in out and "2016" in out
    assert "Jose A. Diaz-Garcia 외 1명" in out


async def test_search_sort_params(tools, monkeypatch, recording_http):
    http = recording_http(ret=EMPTY_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](
        query="all:graphene", sort_by="submittedDate", sort_order="descending"
    )
    assert http.last["params"]["sortBy"] == "submittedDate"
    assert http.last["params"]["sortOrder"] == "descending"
    assert "검색 결과 없음" in out and "총 0건" in out


async def test_search_bad_max_results_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=FEED_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x", max_results=30001)
    assert "max_results" in out and "30000" in out
    assert not http.calls  # 계약 위반은 HTTP 전에 막힘


async def test_search_bad_sort_by_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=FEED_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x", sort_by="date")
    assert "sort_by" in out
    assert not http.calls


# ─── get (id_list) ──────────────────────────────────────────


async def test_get_single_detail(tools, monkeypatch, recording_http):
    http = recording_http(ret=FEED_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)

    out = await tools["arxiv_get"](id_list="1605.08386")
    assert http.last["params"]["id_list"] == "1605.08386"
    assert "1605.08386v1" in out
    assert "Multimatricvariate distribution" in out
    assert "Jose A. Diaz-Garcia 외 1명" in out
    assert "math.ST" in out  # primary_category
    assert "http://arxiv.org/pdf/1605.08386v1" in out  # PDF 링크
    assert "10.1000/xyz123" in out  # DOI
    assert "J. Stat. 12 (2016)" in out  # journal_ref
    assert "23 pages" in out  # comment
    assert "An abstract here." in out  # summary


async def test_get_multiple_summary_list(tools, monkeypatch, recording_http):
    http = recording_http(ret=TWO_ENTRY_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_get"](id_list="1605.08386,cond-mat/0207270")
    assert "총 2건" in out
    assert "First" in out and "Second" in out
    assert "1605.08386v1" in out and "cond-mat/0207270v1" in out


async def test_get_empty_id_list_no_network(tools, monkeypatch, recording_http):
    http = recording_http(ret=FEED_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_get"](id_list="   ")
    assert "비어" in out
    assert not http.calls


# ─── error-entry (HTTP 200 + title='Error') ────────────────


async def test_get_maps_error_entry(tools, monkeypatch, recording_http):
    # malformed id → arXiv는 HTTP 200 + error feed를 준다. 도구가 깔끔히 매핑.
    http = recording_http(ret=ERROR_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_get"](id_list="oops")
    assert "arXiv 오류" in out
    assert "incorrect id format for oops" in out


async def test_search_maps_error_entry(tools, monkeypatch, recording_http):
    http = recording_http(ret=ERROR_XML)
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x")
    assert "arXiv 오류" in out


# ─── HTTP / 파싱 에러 매핑 ──────────────────────────────────


async def test_search_maps_400(tools, monkeypatch, recording_http):
    # max_results>30000은 계약에서 막히지만, 다른 경로의 400도 매핑되는지 확인.
    http = recording_http(exc=UpstreamError(400, "bad request"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x")
    assert "400" in out


async def test_search_maps_503(tools, monkeypatch, recording_http):
    http = recording_http(exc=UpstreamError(503, "busy"))
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x")
    assert "503" in out


async def test_search_maps_xml_parse_error(tools, monkeypatch, recording_http):
    http = recording_http(ret="<feed><entry>broken")
    monkeypatch.setattr(f"{MOD}.get_text", http)
    out = await tools["arxiv_search"](query="x")
    assert "파싱 실패" in out
