"""arXiv 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·네임스페이스·파라미터 검증(max_results/start/sortBy/sortOrder)·
build_search_params·**Atom XML → 모델 파싱**(피드 메타·entry 필드·error-entry 감지).
HTTP 호출은 일절 하지 않는다.
"""

import xml.etree.ElementTree as ET

import pytest

from arcsolve.services.arxiv.contract import (
    BASE_URL,
    DEFAULT_MAX_RESULTS,
    MAX_RESULTS_PER_REQUEST,
    MAX_RESULTS_TOTAL,
    NS,
    ArxivErrorEntry,
    ArxivFeed,
    build_search_params,
    is_error_feed,
    parse_feed,
    validate_max_results,
    validate_sort_by,
    validate_sort_order,
    validate_start,
)

# 공식 User Manual 응답 예시를 본뜬 Atom 1.0 피드(2 entries) — 네임스페이스/요소 그대로.
FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>1000</opensearch:totalResults>
  <opensearch:startIndex>0</opensearch:startIndex>
  <opensearch:itemsPerPage>2</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/1605.08386v1</id>
    <title>Multimatricvariate
       distribution</title>
    <summary>  A line one.
       A line two.  </summary>
    <published>2016-05-26T17:59:02Z</published>
    <updated>2016-05-27T10:00:00Z</updated>
    <author>
      <name>Jose A. Diaz-Garcia</name>
      <arxiv:affiliation>CIMAT</arxiv:affiliation>
    </author>
    <author>
      <name>Ramon Gutierrez-Jaimez</name>
    </author>
    <arxiv:comment>23 pages, 3 figures</arxiv:comment>
    <arxiv:journal_ref>J. Stat. 12 (2016) 1-10</arxiv:journal_ref>
    <arxiv:doi>10.1000/xyz123</arxiv:doi>
    <link href="http://arxiv.org/abs/1605.08386v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/1605.08386v1" rel="related"
          type="application/pdf"/>
    <link title="doi" href="http://dx.doi.org/10.1000/xyz123" rel="related"/>
    <category term="math.ST" scheme="http://arxiv.org/schemas/atom"/>
    <category term="stat.TH" scheme="http://arxiv.org/schemas/atom"/>
    <arxiv:primary_category term="math.ST" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/cond-mat/0207270v1</id>
    <title>A second paper</title>
    <summary>Second abstract.</summary>
    <published>2002-07-11T00:00:00Z</published>
    <author><name>Solo Author</name></author>
    <arxiv:primary_category term="cond-mat" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/cond-mat/0207270v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""

# 잘못된 id에 대한 arXiv error feed — HTTP 200 + 단일 entry title='Error', id가 errors# URL.
ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_1234.12345</id>
    <title>Error</title>
    <summary>incorrect id format for 1234.12345</summary>
  </entry>
</feed>"""


# ─── 상수 / 네임스페이스 ────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://export.arxiv.org/api/query"
    assert DEFAULT_MAX_RESULTS == 10
    assert MAX_RESULTS_PER_REQUEST == 2000
    assert MAX_RESULTS_TOTAL == 30000


def test_namespaces_match_official():
    assert NS["atom"] == "http://www.w3.org/2005/Atom"
    assert NS["opensearch"] == "http://a9.com/-/spec/opensearch/1.1/"
    assert NS["arxiv"] == "http://arxiv.org/schemas/atom"


# ─── 파라미터 검증 ──────────────────────────────────────────


def test_validate_max_results_bounds():
    assert validate_max_results(0) == 0
    assert validate_max_results(MAX_RESULTS_TOTAL) == 30000
    with pytest.raises(ValueError):
        validate_max_results(-1)
    with pytest.raises(ValueError):
        validate_max_results(MAX_RESULTS_TOTAL + 1)


def test_validate_start_bounds():
    assert validate_start(0) == 0
    assert validate_start(100) == 100
    with pytest.raises(ValueError):
        validate_start(-1)


def test_validate_sort_by():
    for v in ("relevance", "lastUpdatedDate", "submittedDate"):
        assert validate_sort_by(v) == v
    with pytest.raises(ValueError):
        validate_sort_by("date")


def test_validate_sort_order():
    assert validate_sort_order("ascending") == "ascending"
    assert validate_sort_order("descending") == "descending"
    with pytest.raises(ValueError):
        validate_sort_order("asc")


# ─── build_search_params ───────────────────────────────────


def test_build_params_omits_none():
    assert build_search_params() == {}


def test_build_params_search_query_and_sort():
    p = build_search_params(
        search_query="ti:electron AND au:hooft",
        start=10,
        max_results=25,
        sort_by="submittedDate",
        sort_order="descending",
    )
    assert p["search_query"] == "ti:electron AND au:hooft"  # 불리언 문자열 그대로
    assert p["start"] == 10
    assert p["max_results"] == 25
    assert p["sortBy"] == "submittedDate"  # camelCase 파라미터명
    assert p["sortOrder"] == "descending"


def test_build_params_id_list():
    p = build_search_params(id_list="1605.08386,cond-mat/0207270v1")
    assert p["id_list"] == "1605.08386,cond-mat/0207270v1"
    assert "search_query" not in p


def test_build_params_rejects_bad_max_results():
    with pytest.raises(ValueError):
        build_search_params(max_results=MAX_RESULTS_TOTAL + 1)


def test_build_params_rejects_bad_start():
    with pytest.raises(ValueError):
        build_search_params(start=-1)


def test_build_params_rejects_bad_sort():
    with pytest.raises(ValueError):
        build_search_params(sort_by="newest")
    with pytest.raises(ValueError):
        build_search_params(sort_order="up")


# ─── XML → 모델 파싱 (정상 피드) ────────────────────────────


def test_parse_feed_opensearch_meta():
    feed = parse_feed(FEED_XML)
    assert isinstance(feed, ArxivFeed)
    assert feed.total_results == 1000
    assert feed.start_index == 0
    assert feed.items_per_page == 2
    assert len(feed.entries) == 2


def test_parse_feed_entry_fields_and_namespaces():
    feed = parse_feed(FEED_XML)
    e = feed.entries[0]
    assert e.id == "http://arxiv.org/abs/1605.08386v1"
    # title/summary는 줄바꿈·연속 공백이 한 칸으로 정규화된다.
    assert e.title == "Multimatricvariate distribution"
    assert e.summary == "A line one. A line two."
    assert e.published == "2016-05-26T17:59:02Z"
    assert e.updated == "2016-05-27T10:00:00Z"
    # arxiv: 네임스페이스 요소
    assert e.comment == "23 pages, 3 figures"
    assert e.journal_ref == "J. Stat. 12 (2016) 1-10"
    assert e.doi == "10.1000/xyz123"
    assert e.primary_category == "math.ST"


def test_parse_feed_authors_with_affiliation():
    e = parse_feed(FEED_XML).entries[0]
    assert len(e.authors) == 2
    assert e.authors[0].name == "Jose A. Diaz-Garcia"
    assert e.authors[0].affiliation == "CIMAT"  # arxiv:affiliation
    assert e.authors[1].name == "Ramon Gutierrez-Jaimez"
    assert e.authors[1].affiliation is None


def test_parse_feed_links_and_categories():
    e = parse_feed(FEED_XML).entries[0]
    # abstract(alternate) + pdf + doi = 3개 링크
    assert len(e.links) == 3
    by_title = {ln.title: ln for ln in e.links}
    assert by_title["pdf"].href == "http://arxiv.org/pdf/1605.08386v1"
    assert by_title["pdf"].rel == "related"
    assert by_title["doi"].href == "http://dx.doi.org/10.1000/xyz123"
    alt = [ln for ln in e.links if ln.rel == "alternate"][0]
    assert alt.type == "text/html"
    # category term/scheme
    terms = [c.term for c in e.categories]
    assert terms == ["math.ST", "stat.TH"]
    assert e.categories[0].scheme == "http://arxiv.org/schemas/atom"


def test_parse_feed_second_entry_minimal():
    e = parse_feed(FEED_XML).entries[1]
    assert e.id.endswith("cond-mat/0207270v1")
    assert e.title == "A second paper"
    assert len(e.authors) == 1
    assert e.comment is None and e.doi is None  # 선택 요소 없음


# ─── error-entry 감지 ──────────────────────────────────────


def test_is_error_feed_detects_error():
    root = ET.fromstring(ERROR_XML)
    assert is_error_feed(root) is True


def test_is_error_feed_false_for_normal():
    root = ET.fromstring(FEED_XML)
    assert is_error_feed(root) is False


def test_is_error_feed_does_not_misfire_on_title_error_paper():
    # 정상 논문 제목이 우연히 'Error'여도 id가 abs URL이면 에러로 오탐하지 않는다.
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2101.00001v1</id>
        <title>Error</title>
        <summary>A real paper titled Error.</summary>
      </entry>
    </feed>"""
    root = ET.fromstring(xml)
    assert is_error_feed(root) is False


def test_parse_feed_returns_error_entry():
    result = parse_feed(ERROR_XML)
    assert isinstance(result, ArxivErrorEntry)
    assert result.summary == "incorrect id format for 1234.12345"
    assert "/api/errors" in result.id


def test_parse_feed_raises_on_malformed_xml():
    with pytest.raises(ET.ParseError):
        parse_feed("<feed><entry>broken")
