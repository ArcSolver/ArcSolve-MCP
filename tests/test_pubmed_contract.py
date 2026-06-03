"""PubMed 계약 검증 — 네트워크 없이 contract.py만 테스트.

검증 범위: 상수·파라미터 검증(retmax/retstart/sort/normalize_ids)·build_*_params(JSON 빌더)·
**esearch/esummary JSON 파싱**·**efetch abstract XML 파싱**(구조화 초록 라벨 포함). HTTP 없음.
"""

import xml.etree.ElementTree as ET

import pytest

from arcsolve.services.pubmed.contract import (
    BASE_URL,
    DB_PUBMED,
    DEFAULT_RETMAX,
    EFETCH,
    ESEARCH,
    ESUMMARY,
    MAX_IDS,
    MAX_RETMAX,
    ArticleSummary,
    ESearchResult,
    build_fetch_params,
    build_search_params,
    build_summary_params,
    normalize_ids,
    parse_abstracts,
    parse_esearch,
    parse_esummary,
    search_error,
    validate_retmax,
    validate_retstart,
    validate_sort,
)

# 라이브 esearch JSON(uid 형태) — count/retmax/retstart가 문자열로 온다(라이브 확인).
ESEARCH_JSON = {
    "header": {"type": "esearch", "version": "0.3"},
    "esearchresult": {
        "count": "67815",
        "retmax": "2",
        "retstart": "0",
        "idlist": ["42233250", "42232503"],
        "querytranslation": "crispr[All Fields]",
    },
}

# 잘못된 검색식 → HTTP 200 + ERROR 키(라이브 관찰 형태).
ESEARCH_ERROR_JSON = {"esearchresult": {"ERROR": "Invalid field tag", "idlist": []}}

# 라이브 esummary JSON(uid 31452104) 부분 — authors{name,authtype}·articleids{idtype,value}.
ESUMMARY_JSON = {
    "header": {"type": "esummary", "version": "0.3"},
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
            "issue": "",
            "pages": "149-167",
            "elocationid": "doi: 10.1007/978-1-4939-9752-7_10",
            "articleids": [
                {"idtype": "pubmed", "idtypen": 1, "value": "31452104"},
                {"idtype": "doi", "idtypen": 3, "value": "10.1007/978-1-4939-9752-7_10"},
            ],
        },
    },
}

# 없는 id → uid 오브젝트에 error 키만(라이브 관찰).
ESUMMARY_ERROR_JSON = {
    "result": {"uids": ["999999999"], "999999999": {"uid": "999999999", "error": "cannot get document summary"}}
}

# 라이브 efetch abstract XML(uid 31452104) — 단순(라벨 없는) 초록.
EFETCH_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle><MedlineCitation Status="MEDLINE"><PMID Version="1">31452104</PMID>
<Article PubModel="Print"><Journal><Title>Methods in molecular biology (Clifton, N.J.)</Title>
<ISOAbbreviation>Methods Mol Biol</ISOAbbreviation></Journal>
<ArticleTitle>Molegro Virtual Docker for Docking.</ArticleTitle>
<Abstract><AbstractText>Molegro Virtual Docker is a protein-ligand docking program.</AbstractText></Abstract>
</Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""

# 구조화 초록(라이브 확인 uid 32109013) — AbstractText@Label 다수.
EFETCH_STRUCTURED_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID Version="1">32109013</PMID>
<Article><Journal><Title>Some Journal</Title></Journal>
<ArticleTitle>A structured study.</ArticleTitle>
<Abstract>
<AbstractText Label="BACKGROUND">Bg text.</AbstractText>
<AbstractText Label="METHODS">Methods text.</AbstractText>
<AbstractText Label="RESULTS">Results text.</AbstractText>
</Abstract></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""

# 초록 없는 레코드(예: 일부 챕터) — Abstract 요소 자체가 없음.
EFETCH_NO_ABSTRACT_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID Version="1">11111111</PMID>
<Article><Journal><ISOAbbreviation>J Abbr</ISOAbbreviation></Journal>
<ArticleTitle>No abstract here.</ArticleTitle></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""

# 없는 PMID → 빈 set(라이브 확인).
EFETCH_EMPTY_XML = '<?xml version="1.0" ?><PubmedArticleSet></PubmedArticleSet>'


# ─── 상수 ───────────────────────────────────────────────────


def test_constants_match_official():
    assert BASE_URL == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    assert ESEARCH == "esearch.fcgi"
    assert ESUMMARY == "esummary.fcgi"
    assert EFETCH == "efetch.fcgi"
    assert DB_PUBMED == "pubmed"
    assert DEFAULT_RETMAX == 20
    assert MAX_RETMAX == 10000
    assert MAX_IDS == 200


# ─── 파라미터 검증 ──────────────────────────────────────────


def test_validate_retmax_bounds():
    assert validate_retmax(0) == 0
    assert validate_retmax(MAX_RETMAX) == 10000
    with pytest.raises(ValueError):
        validate_retmax(-1)
    with pytest.raises(ValueError):
        validate_retmax(MAX_RETMAX + 1)


def test_validate_retstart_bounds():
    assert validate_retstart(0) == 0
    assert validate_retstart(40) == 40
    with pytest.raises(ValueError):
        validate_retstart(-1)


def test_validate_sort():
    for v in ("relevance", "pub_date", "Author", "JournalName"):
        assert validate_sort(v) == v
    with pytest.raises(ValueError):
        validate_sort("date")


def test_normalize_ids_trims_and_joins():
    assert normalize_ids(" 31452104, 23092060 ") == "31452104,23092060"
    assert normalize_ids("1,,2,") == "1,2"  # 빈 항목 제거


def test_normalize_ids_rejects_empty():
    with pytest.raises(ValueError):
        normalize_ids("   ")


def test_normalize_ids_rejects_too_many():
    too_many = ",".join(str(i) for i in range(MAX_IDS + 1))
    with pytest.raises(ValueError):
        normalize_ids(too_many)


# ─── build_*_params (JSON/XML 분담 고정) ────────────────────


def test_build_search_params_defaults_json():
    p = build_search_params(term="crispr AND cas9[ti]")
    assert p["db"] == "pubmed"
    assert p["term"] == "crispr AND cas9[ti]"  # 검색식 그대로
    assert p["retmode"] == "json"  # esearch는 JSON
    assert "retmax" not in p and "sort" not in p  # None 생략


def test_build_search_params_with_options():
    p = build_search_params(term="x", retmax=5, retstart=10, sort="pub_date")
    assert p["retmax"] == 5
    assert p["retstart"] == 10
    assert p["sort"] == "pub_date"


def test_build_search_params_rejects_bad_values():
    with pytest.raises(ValueError):
        build_search_params(term="x", retmax=MAX_RETMAX + 1)
    with pytest.raises(ValueError):
        build_search_params(term="x", retstart=-1)
    with pytest.raises(ValueError):
        build_search_params(term="x", sort="newest")


def test_build_summary_params_json():
    p = build_summary_params(ids=" 31452104 , 23092060 ")
    assert p == {"db": "pubmed", "id": "31452104,23092060", "retmode": "json"}


def test_build_fetch_params_xml_abstract():
    # efetch는 JSON 미지원 → rettype=abstract & retmode=xml 고정.
    p = build_fetch_params(ids="31452104")
    assert p == {
        "db": "pubmed",
        "id": "31452104",
        "rettype": "abstract",
        "retmode": "xml",
    }
    assert "json" not in p.values()


# ─── esearch JSON 파싱 ──────────────────────────────────────


def test_parse_esearch_coerces_string_numbers():
    r = parse_esearch(ESEARCH_JSON)
    assert isinstance(r, ESearchResult)
    assert r.count == 67815  # 문자열 "67815" → int
    assert r.retmax == 2
    assert r.retstart == 0
    assert r.idlist == ["42233250", "42232503"]


def test_parse_esearch_empty_body():
    r = parse_esearch({})
    assert r.count is None and r.idlist == []


def test_search_error_detects_and_absent():
    assert search_error(ESEARCH_ERROR_JSON) == "Invalid field tag"
    assert search_error(ESEARCH_JSON) is None  # 정상 응답엔 ERROR 없음


# ─── esummary JSON 파싱 ─────────────────────────────────────


def test_parse_esummary_fields_and_doi():
    out = parse_esummary(ESUMMARY_JSON)
    assert len(out) == 1
    a = out[0]
    assert isinstance(a, ArticleSummary)
    assert a.uid == "31452104"
    assert a.title == "Molegro Virtual Docker for Docking."
    assert len(a.authors) == 2
    assert a.authors[0].name == "Bitencourt-Ferreira G"
    assert a.authors[0].authtype == "Author"
    assert a.source == "Methods Mol Biol"
    assert a.fulljournalname == "Methods in molecular biology (Clifton, N.J.)"
    assert a.pubdate == "2019"
    assert a.volume == "2053"
    assert a.pages == "149-167"
    # DOI는 articleids에서 idtype='doi'로 추출
    assert a.doi == "10.1007/978-1-4939-9752-7_10"


def test_parse_esummary_keeps_order_of_uids():
    body = {
        "result": {
            "uids": ["2", "1"],
            "1": {"uid": "1", "title": "First"},
            "2": {"uid": "2", "title": "Second"},
        }
    }
    out = parse_esummary(body)
    assert [a.uid for a in out] == ["2", "1"]  # uids 순서 유지


def test_parse_esummary_error_record_kept_without_title():
    out = parse_esummary(ESUMMARY_ERROR_JSON)
    assert len(out) == 1
    assert out[0].uid == "999999999"
    assert out[0].title is None  # error 레코드는 title 없음


# ─── efetch abstract XML 파싱 ───────────────────────────────


def test_parse_abstracts_simple():
    arts = parse_abstracts(EFETCH_XML)
    assert len(arts) == 1
    a = arts[0]
    assert a.pmid == "31452104"
    assert a.title == "Molegro Virtual Docker for Docking."
    assert a.abstract == "Molegro Virtual Docker is a protein-ligand docking program."
    assert a.journal == "Methods in molecular biology (Clifton, N.J.)"


def test_parse_abstracts_structured_labels():
    a = parse_abstracts(EFETCH_STRUCTURED_XML)[0]
    # 구조화 초록은 'LABEL: 본문'을 줄바꿈 결합.
    assert "BACKGROUND: Bg text." in a.abstract
    assert "METHODS: Methods text." in a.abstract
    assert "RESULTS: Results text." in a.abstract
    assert a.abstract.count("\n") == 2


def test_parse_abstracts_no_abstract_is_none():
    a = parse_abstracts(EFETCH_NO_ABSTRACT_XML)[0]
    assert a.pmid == "11111111"
    assert a.abstract is None
    assert a.journal == "J Abbr"  # ISOAbbreviation 폴백


def test_parse_abstracts_empty_set():
    assert parse_abstracts(EFETCH_EMPTY_XML) == []


def test_parse_abstracts_raises_on_malformed_xml():
    with pytest.raises(ET.ParseError):
        parse_abstracts("<PubmedArticleSet><PubmedArticle>broken")
