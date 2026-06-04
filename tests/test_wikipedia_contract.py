"""Wikipedia 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수(호스트·경로·기본 User-Agent)·언어/limit/exchars 검증·제목 인코더·HTML 스트립·
쿼리 빌더·부분 응답 모델 파싱(REST 검색 pages[]·요약 최상위(wikibase_item·coordinates)·
TextExtracts formatversion=2 배열·missing 페이지·links/categories·Action 에러 봉투).
HTTP 호출은 일절 하지 않는다.
"""

import pytest

from arcsolve.services.wikipedia.contract import (
    ACTION_API_PATH,
    DEFAULT_USER_AGENT,
    MAX_EXCHARS,
    MAX_LINKS_LIMIT,
    MAX_SEARCH_LIMIT,
    REST_SEARCH_PATH,
    REST_V1_SUMMARY_PREFIX,
    ActionError,
    ExtractPage,
    LinksPage,
    SearchResponse,
    SummaryResponse,
    encode_title,
    extracts_params,
    links_params,
    strip_html,
    summary_path,
    validate_exchars,
    validate_lang,
    validate_limit,
    wiki_host,
)


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert REST_SEARCH_PATH == "/w/rest.php/v1/search/page"
    assert REST_V1_SUMMARY_PREFIX == "/api/rest_v1/page/summary/"
    assert ACTION_API_PATH == "/w/api.php"
    assert "arcsolve" in DEFAULT_USER_AGENT
    assert "ArcSolver/ArcSolve-Kit" in DEFAULT_USER_AGENT


def test_wiki_host_per_language():
    assert wiki_host("en") == "https://en.wikipedia.org"
    assert wiki_host("ko") == "https://ko.wikipedia.org"
    assert wiki_host("simple") == "https://simple.wikipedia.org"


# ─── 제목 인코더 / 경로 빌더 ───────────────────────────────


def test_encode_title_encodes_space_and_slash():
    # path segment라 슬래시도 인코딩(%2F), 공백은 %20.
    assert encode_title("Quantum computing") == "Quantum%20computing"
    assert encode_title("AC/DC") == "AC%2FDC"
    assert encode_title("  Paris  ") == "Paris"  # 트림


def test_summary_path_builds_encoded_segment():
    assert summary_path("Quantum computing") == ("/api/rest_v1/page/summary/Quantum%20computing")


# ─── 언어 / limit / exchars 검증 ───────────────────────────


def test_validate_lang_normalizes_and_accepts_variants():
    assert validate_lang("EN") == "en"  # 소문자화
    assert validate_lang("  ko ") == "ko"  # 트림
    assert validate_lang("simple") == "simple"
    assert validate_lang("zh-yue") == "zh-yue"  # 하이픈 변형 허용


def test_validate_lang_rejects_bad_format():
    for bad in ("en_US", "en1", "EN US", "", "..", "zh/yue"):
        with pytest.raises(ValueError):
            validate_lang(bad)


def test_validate_limit_bounds():
    assert validate_limit(1, maximum=MAX_SEARCH_LIMIT) == 1
    assert validate_limit(100, maximum=MAX_SEARCH_LIMIT) == 100
    assert validate_limit(500, maximum=MAX_LINKS_LIMIT) == 500
    with pytest.raises(ValueError):
        validate_limit(0, maximum=MAX_SEARCH_LIMIT)
    with pytest.raises(ValueError):
        validate_limit(101, maximum=MAX_SEARCH_LIMIT)  # 검색 상한 100
    with pytest.raises(ValueError):
        validate_limit(501, maximum=MAX_LINKS_LIMIT)  # 링크 상한 500


def test_validate_exchars_bounds():
    assert validate_exchars(1) == 1
    assert validate_exchars(MAX_EXCHARS) == 1200
    with pytest.raises(ValueError):
        validate_exchars(0)
    with pytest.raises(ValueError):
        validate_exchars(1201)


# ─── HTML 스트립 ────────────────────────────────────────────


def test_strip_html_removes_tags_and_unescapes():
    snippet = (
        '<span class="searchmatch">quantum</span> computing (abbreviated &#039;n.&#039;) &amp; more'
    )
    out = strip_html(snippet)
    assert "<span" not in out and "searchmatch" not in out
    assert out == "quantum computing (abbreviated 'n.') & more"


def test_strip_html_empty():
    assert strip_html(None) == ""
    assert strip_html("") == ""


# ─── 쿼리 빌더 (Action API) ───────────────────────────────


def test_extracts_params_intro_and_exchars():
    p = extracts_params("Paris", intro_only=True, max_chars=200)
    assert p["action"] == "query"
    assert p["prop"] == "extracts"
    assert p["explaintext"] == 1
    assert p["formatversion"] == 2  # 배열 응답
    assert p["redirects"] == 1
    assert p["exintro"] == 1
    assert p["exchars"] == 200
    assert p["titles"] == "Paris"


def test_extracts_params_full_text_no_exchars():
    p = extracts_params("Paris", intro_only=False)
    assert "exintro" not in p  # 전체 본문
    assert "exchars" not in p


def test_links_params():
    p = links_params("Python", limit=3)
    assert p["prop"] == "links|categories"
    assert p["plnamespace"] == 0
    assert p["pllimit"] == 3
    assert p["cllimit"] == 3
    assert p["formatversion"] == 2
    assert p["redirects"] == 1
    assert p["titles"] == "Python"


# ─── 응답 모델 ──────────────────────────────────────────────


def test_search_response_parsing():
    # 라이브: REST 검색 응답엔 total 필드가 없다.
    body = {
        "pages": [
            {
                "id": 25220,
                "key": "Quantum_computing",
                "title": "Quantum computing",
                "excerpt": '<span class="searchmatch">quantum</span> computing',
                "matched_title": None,
                "description": "Computer hardware technology that uses quantum mechanics",
                "thumbnail": {
                    "mimetype": "image/jpeg",
                    "width": 60,
                    "height": 80,
                    "url": "//upload.wikimedia.org/x.jpg",
                },
                "extra": "ignored",
            }
        ]
    }
    r = SearchResponse.model_validate(body)
    assert len(r.pages) == 1
    p = r.pages[0]
    assert p.key == "Quantum_computing"
    assert p.title == "Quantum computing"
    assert p.description.startswith("Computer hardware")
    assert p.thumbnail.url == "//upload.wikimedia.org/x.jpg"
    # excerpt는 HTML — 스트립 헬퍼로 평문화.
    assert strip_html(p.excerpt) == "quantum computing"


def test_summary_response_fields_including_wikibase_and_coordinates():
    body = {
        "type": "standard",
        "title": "Paris",
        "description": "Capital of France",
        "extract": "Paris is the capital and largest city of France.",
        "lang": "en",
        "wikibase_item": "Q90",
        "content_urls": {
            "desktop": {
                "page": "https://en.wikipedia.org/wiki/Paris",
                "edit": "https://en.wikipedia.org/wiki/Paris?action=edit",
            },
            "mobile": {"page": "https://en.m.wikipedia.org/wiki/Paris"},
        },
        "thumbnail": {"source": "https://upload.wikimedia.org/paris.jpg", "width": 320},
        "coordinates": {"lat": 48.8567, "lon": 2.3522},
        "extra": "ignored",
    }
    sm = SummaryResponse.model_validate(body)
    assert sm.type == "standard"
    assert sm.title == "Paris"
    assert sm.wikibase_item == "Q90"  # Wikidata Q-id 브리지
    assert sm.content_urls.desktop.page == "https://en.wikipedia.org/wiki/Paris"
    assert sm.thumbnail.source.endswith("paris.jpg")
    assert sm.coordinates.lat == 48.8567 and sm.coordinates.lon == 2.3522


def test_summary_response_disambiguation_without_coordinates():
    body = {"type": "disambiguation", "title": "Mercury", "extract": "Mercury may refer to ..."}
    sm = SummaryResponse.model_validate(body)
    assert sm.type == "disambiguation"
    assert sm.coordinates is None  # 비-지리 문서엔 좌표 없음
    assert sm.wikibase_item is None


def test_extract_page_formatversion2_array_shape():
    # formatversion=2 → query.pages가 깨끗한 배열(pageid-keyed 객체 아님).
    body = {
        "batchcomplete": True,
        "query": {
            "pages": [
                {
                    "pageid": 23862,
                    "ns": 0,
                    "title": "Python (programming language)",
                    "extract": "Python is a high-level language.",
                }
            ]
        },
    }
    pages = body["query"]["pages"]
    assert isinstance(pages, list)  # 배열
    page = ExtractPage.model_validate(pages[0])
    assert page.pageid == 23862
    assert page.title.startswith("Python")
    assert page.extract.startswith("Python is")
    assert page.missing is None


def test_extract_page_missing():
    page = ExtractPage.model_validate({"ns": 0, "title": "ZZZNope", "missing": True})
    assert page.missing is True
    assert page.extract is None


def test_links_page_with_links_and_categories():
    page = LinksPage.model_validate(
        {
            "pageid": 23862,
            "ns": 0,
            "title": "Python (programming language)",
            "links": [
                {"ns": 0, "title": '"Hello, World!" program'},
                {"ns": 0, "title": "ALGOL 68"},
            ],
            "categories": [
                {"ns": 14, "title": "Category:Programming languages"},
            ],
        }
    )
    assert page.title.startswith("Python")
    assert len(page.links) == 2
    assert page.links[0].title == '"Hello, World!" program'
    assert page.categories[0].title == "Category:Programming languages"
    assert page.missing is None


def test_links_page_absent_links_default_empty():
    # links/categories는 둘 다 없을 수 있다 → 기본 빈 리스트.
    page = LinksPage.model_validate({"pageid": 1, "title": "Stub"})
    assert page.links == []
    assert page.categories == []


def test_links_page_missing():
    page = LinksPage.model_validate({"title": "ZZZNope", "missing": True})
    assert page.missing is True


def test_action_error_envelope():
    # 라이브: action=nonsense → HTTP 200 + {"error":{"code":"badvalue","info":...}}.
    err = ActionError.model_validate(
        {
            "code": "badvalue",
            "info": 'Unrecognized value for parameter "action": nonsense.',
            "*": "docref...",
        }
    )
    assert err.code == "badvalue"
    assert "Unrecognized value" in err.info
