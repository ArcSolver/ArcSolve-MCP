"""PubMed(NCBI E-utilities) 생의학 문헌 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, JSON/XML 응답 파싱.
MCP/네트워크 무의존(순수 상수 + pydantic 모델 + 표준 라이브러리 XML 파서).

전부 GET·읽기. 인증은 **선택**(키 없이도 동작). 키(`api_key`)와 식별용 `tool`/`email`은
**쿼리 파라미터**다(헤더 아님). E-utilities는 도구마다 응답 포맷이 다르다:
  - esearch / esummary → `retmode=json` JSON → 코어 `get_json`
  - efetch(abstract) → **XML만 지원(JSON 미지원)** → 코어 `get_text`(raw str) + 표준 라이브러리
    `xml.etree.ElementTree`로 파싱(feedparser/lxml 같은 외부 의존 금지).

출처(공식 문서 — ncbi.nlm.nih.gov/books):
  - E-utilities Quick Start(개요·base URL·esearch/esummary/efetch 흐름):
    https://www.ncbi.nlm.nih.gov/books/NBK25500/
  - E-utilities In-Depth(전 파라미터·retmode·sort·api_key·tool/email·JSON 출력 구조):
    https://www.ncbi.nlm.nih.gov/books/NBK25499/
  - General Introduction(레이트리밋 3/s·10/s·api_key·tool/email 등록 요구):
    https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base): NBK25497 General Introduction
#   ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/")
# 출처(유틸 이름): NBK25500 Quick Start (esearch.fcgi / esummary.fcgi / efetch.fcgi)
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
ESEARCH = "esearch.fcgi"
ESUMMARY = "esummary.fcgi"
EFETCH = "efetch.fcgi"

# 고정 db — 이 서비스는 PubMed만 다룬다(스코프 밖: 다른 db).
# 출처: NBK25499 In-Depth (db 파라미터, default pubmed).
DB_PUBMED = "pubmed"

# ─── 쿼리 파라미터명(공식 철자) ─────────────────────────────
# 출처: NBK25499 In-Depth (db·term·id·retmax·retstart·retmode·rettype·sort·api_key)
#       + NBK25497 (tool·email)
PARAM_DB = "db"
PARAM_TERM = "term"
PARAM_ID = "id"
PARAM_RETMAX = "retmax"
PARAM_RETSTART = "retstart"
PARAM_RETMODE = "retmode"
PARAM_RETTYPE = "rettype"
PARAM_SORT = "sort"
PARAM_API_KEY = "api_key"
PARAM_TOOL = "tool"
PARAM_EMAIL = "email"

# retmode/rettype 값(공식).
# 출처: NBK25499 — esearch/esummary retmode 'xml'(기본) 또는 'json';
#       efetch(pubmed) rettype='abstract', retmode 'xml' 또는 'text'(JSON 미지원).
RETMODE_JSON = "json"
RETMODE_XML = "xml"
RETTYPE_ABSTRACT = "abstract"

# ─── retmax 제약(공식) ──────────────────────────────────────
# 출처: NBK25499 In-Depth (esearch retmax: "default=20", "maximum=10,000"; retstart default=0).
DEFAULT_RETMAX = 20
MAX_RETMAX = 10000

# sort 허용값(esearch/pubmed, 공식). 출처: NBK25499 In-Depth
#   (pub_date·Author·JournalName·relevance). relevance가 "Best Match"(미지정 시 기본).
SORT_RELEVANCE = "relevance"
SORT_PUB_DATE = "pub_date"
SORT_AUTHOR = "Author"
SORT_JOURNAL = "JournalName"
VALID_SORT = (SORT_RELEVANCE, SORT_PUB_DATE, SORT_AUTHOR, SORT_JOURNAL)

# id 1회 요청 권장 상한 — esummary/efetch는 콤마 구분 UID 목록을 받는다. GET URL 길이를 고려한
# 가드(공식 문서는 약 200개 초과 시 POST 권장; 여기선 단순 GET이라 보수적으로 제한).
# 출처: NBK25499 In-Depth ("If more than about 200 UIDs are to be provided, ... use the HTTP POST").
MAX_IDS = 200


def validate_retmax(retmax: int) -> int:
    """retmax를 0..10000 범위로 검증한다(공식 상한).

    위반 시 ValueError(상류 전에 미리 막는다).
    출처: NBK25499 In-Depth (esearch retmax default=20, maximum=10,000).
    """
    if retmax < 0 or retmax > MAX_RETMAX:
        raise ValueError(f"retmax는 0..{MAX_RETMAX} 범위여야 합니다(현재 {retmax}).")
    return retmax


def validate_retstart(retstart: int) -> int:
    """retstart를 0 이상으로 검증한다(0-based 오프셋, 공식).

    출처: NBK25499 In-Depth (esearch retstart "default=0").
    """
    if retstart < 0:
        raise ValueError(f"retstart는 0 이상이어야 합니다(현재 {retstart}).")
    return retstart


def validate_sort(sort: str) -> str:
    """sort를 relevance/pub_date/Author/JournalName로 검증한다(공식 esearch pubmed 값)."""
    if sort not in VALID_SORT:
        raise ValueError(f"sort는 {VALID_SORT} 중 하나여야 합니다(현재 {sort!r}).")
    return sort


def normalize_ids(ids: str) -> str:
    """콤마 구분 PMID 문자열을 정리한다(공백 제거·빈 항목 제거).

    예: ` 31452104, 23092060 ` → `31452104,23092060`. 1회 MAX_IDS개 초과면 ValueError.
    출처: NBK25499 In-Depth (id = "comma-delimited list of UIDs").
    """
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if not parts:
        raise ValueError("id 목록이 비어 있습니다. PMID를 콤마로 구분해 입력하세요.")
    if len(parts) > MAX_IDS:
        raise ValueError(
            f"id는 1회 최대 {MAX_IDS}개까지 권장합니다(현재 {len(parts)}개). "
            f"그 이상은 분할 요청하세요."
        )
    return ",".join(parts)


def build_search_params(
    *,
    term: str,
    retmax: int | None = None,
    retstart: int | None = None,
    sort: str | None = None,
) -> dict[str, str | int]:
    """esearch 쿼리스트링을 만든다(retmode=json 고정·db=pubmed). None/빈값은 생략.

    - term → `term`(Entrez 검색식 그대로 전달; 필드 태그·불리언은 호출자 책임. 빌더 안 함 — 스코프 밖).
    - retmax → `retmax`(0..10000 검증).
    - retstart → `retstart`(0-based 오프셋, 검증).
    - sort → `sort`(relevance/pub_date/Author/JournalName 검증).
    출처: NBK25499 In-Depth (esearch term·retmax·retstart·retmode=json·sort).
    """
    params: dict[str, str | int] = {
        PARAM_DB: DB_PUBMED,
        PARAM_TERM: term,
        PARAM_RETMODE: RETMODE_JSON,
    }
    if retmax is not None:
        params[PARAM_RETMAX] = validate_retmax(retmax)
    if retstart is not None:
        params[PARAM_RETSTART] = validate_retstart(retstart)
    if sort is not None:
        params[PARAM_SORT] = validate_sort(sort)
    return params


def build_summary_params(*, ids: str) -> dict[str, str]:
    """esummary 쿼리스트링을 만든다(retmode=json 고정·db=pubmed).

    ids는 normalize_ids로 정리된 콤마 구분 PMID 목록.
    출처: NBK25499 In-Depth (esummary db·id·retmode=json).
    """
    return {
        PARAM_DB: DB_PUBMED,
        PARAM_ID: normalize_ids(ids),
        PARAM_RETMODE: RETMODE_JSON,
    }


def build_fetch_params(*, ids: str) -> dict[str, str]:
    """efetch 쿼리스트링을 만든다(rettype=abstract·retmode=xml 고정·db=pubmed).

    efetch(pubmed)는 JSON을 지원하지 않으므로 XML로 받는다 → 호출부는 get_text + parse_abstracts.
    출처: NBK25499 In-Depth (efetch pubmed rettype=abstract, retmode xml/text — JSON 미지원).
    """
    return {
        PARAM_DB: DB_PUBMED,
        PARAM_ID: normalize_ids(ids),
        PARAM_RETTYPE: RETTYPE_ABSTRACT,
        PARAM_RETMODE: RETMODE_XML,
    }


# ─── esearch JSON → 모델 ────────────────────────────────────
# esearch JSON 봉투: {"header":{...}, "esearchresult":{count, retmax, retstart, idlist:[...]}}.
# 라이브 확인: count/retmax/retstart는 **문자열**로 온다(예: "count":"67815"). int로 강제 변환.
# 출처: NBK25499 In-Depth (esearchresult: count·retmax·retstart·idlist) + 라이브 응답.


class ESearchResult(BaseModel):
    """esearch 결과(`esearchresult`) — 부분 모델.

    count(총 매치 수)·retmax·retstart는 상류가 문자열로 주므로 int로 받되 None 허용,
    idlist는 PMID 문자열 배열. translationset/querytranslation 등 부가 필드는 무시.
    출처: NBK25499 In-Depth (esearchresult 구조) + 라이브 응답(필드 문자열).
    """

    count: int | None = None
    retmax: int | None = None
    retstart: int | None = None
    idlist: list[str] = []


def parse_esearch(body: dict) -> ESearchResult:
    """esearch JSON 본문에서 ESearchResult를 만든다.

    `esearchresult` 하위에서 count/retmax/retstart(문자열→int)·idlist를 뽑는다.
    상류가 에러 봉투(`{"esearchresult":{"ERROR":"..."}}`)를 줄 수 있으나 idlist가 비면 빈 결과로 본다.
    """
    r = body.get("esearchresult", {}) if isinstance(body, dict) else {}
    return ESearchResult(
        count=_to_int(r.get("count")),
        retmax=_to_int(r.get("retmax")),
        retstart=_to_int(r.get("retstart")),
        idlist=[str(x) for x in (r.get("idlist") or [])],
    )


def search_error(body: dict) -> str | None:
    """esearch JSON에서 상류 ERROR 메시지를 뽑는다(없으면 None).

    잘못된 검색식 등은 `{"esearchresult":{..., "ERROR":"..."}}` 형태로 HTTP 200에 실릴 수 있다.
    출처: 라이브 관찰(빈 idlist + ERROR 키). querytranslation 등 정상 필드와 구분.
    """
    if not isinstance(body, dict):
        return None
    r = body.get("esearchresult", {})
    err = r.get("ERROR") if isinstance(r, dict) else None
    return str(err) if err else None


# ─── esummary JSON → 모델 ───────────────────────────────────
# esummary JSON 봉투: {"result":{"uids":[...], "<uid>":{title, authors:[{name,authtype}], source,
# pubdate, fulljournalname, volume, issue, pages, elocationid, articleids:[{idtype,value}], ...}}}.
# 라이브 확인(uid 31452104): authors[].name="Bitencourt-Ferreira G", articleids idtype 'doi'/'pubmed'.
# 출처: NBK25499 In-Depth (PubMed DocSum JSON: title·authors{name,authtype}·source·pubdate·
#       articleids{idtype,value}·elocationid·fulljournalname·volume·issue·pages) + 라이브 응답.


class SummaryAuthor(BaseModel):
    """저자 요약(authors[]) — name + authtype.

    출처: NBK25499 In-Depth (authors array: name·authtype) + 라이브 응답.
    """

    name: str | None = None
    authtype: str | None = None


class ArticleSummary(BaseModel):
    """단일 논문 요약(esummary DocSum) — 부분 모델.

    uid(PMID)·title·authors·source(약식 저널)·fulljournalname·pubdate·volume·issue·pages·
    elocationid·doi(articleids에서 idtype='doi' 추출). 그 밖 다수 필드는 무시.
    출처: NBK25499 In-Depth (PubMed DocSum) + 라이브 응답(articleids idtype 'doi').
    """

    uid: str | None = None
    title: str | None = None
    authors: list[SummaryAuthor] = []
    source: str | None = None
    fulljournalname: str | None = None
    pubdate: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    elocationid: str | None = None
    doi: str | None = None


def _doi_from_articleids(articleids: list | None) -> str | None:
    """articleids 배열에서 idtype='doi' 항목의 value를 뽑는다(없으면 None).

    출처: 라이브 응답 ({'idtype':'doi','value':'10.1007/...'}). idtype 표기는 소문자 'doi'.
    """
    for a in articleids or []:
        if isinstance(a, dict) and a.get("idtype") == "doi" and a.get("value"):
            return str(a["value"])
    return None


def parse_esummary(body: dict) -> list[ArticleSummary]:
    """esummary JSON 본문에서 ArticleSummary 목록을 만든다(uids 순서 유지).

    `result.uids` 순서대로 각 uid 오브젝트를 모델로 변환한다. uid에 `error`(예: 'cannot get
    document summary')만 있으면 title 없는 요약으로 두되 uid는 보존한다.
    출처: NBK25499 In-Depth (result keyed by uids) + 라이브(없는 id → uid에 error 키).
    """
    out: list[ArticleSummary] = []
    if not isinstance(body, dict):
        return out
    result = body.get("result", {})
    if not isinstance(result, dict):
        return out
    for uid in result.get("uids", []):
        rec = result.get(str(uid))
        if not isinstance(rec, dict):
            continue
        authors = [
            SummaryAuthor(name=a.get("name"), authtype=a.get("authtype"))
            for a in rec.get("authors", [])
            if isinstance(a, dict)
        ]
        out.append(
            ArticleSummary(
                uid=str(uid),
                title=rec.get("title"),
                authors=authors,
                source=rec.get("source"),
                fulljournalname=rec.get("fulljournalname"),
                pubdate=rec.get("pubdate"),
                volume=rec.get("volume"),
                issue=rec.get("issue"),
                pages=rec.get("pages"),
                elocationid=rec.get("elocationid"),
                doi=_doi_from_articleids(rec.get("articleids")),
            )
        )
    return out


# ─── efetch XML(abstract) → 모델 ────────────────────────────
# efetch(pubmed, rettype=abstract&retmode=xml)는 <PubmedArticleSet>의 <PubmedArticle>* 를 준다.
# 핵심 경로(라이브 확인):
#   PubmedArticle/MedlineCitation/PMID                                → PMID
#   .../Article/ArticleTitle                                          → 제목
#   .../Article/Abstract/AbstractText (다수, Label 속성 가능)         → 초록(구조화 가능)
#   .../Article/Journal/Title, .../Journal/ISOAbbreviation           → 저널
# 구조화 초록은 <AbstractText Label="BACKGROUND"> 등 여러 개로 쪼개진다(라이브 확인 uid 32109013).
# 출처: 라이브 efetch 응답(uid 31452104·23092060·32109013) — PubMed DTD 요소.


class PubmedArticle(BaseModel):
    """efetch에서 추출한 단일 논문(부분 모델).

    pmid·title·abstract(구조화 초록은 'LABEL: 본문'을 줄바꿈으로 결합)·journal.
    초록이 없는 레코드(예: 회의록·일부 서간)는 abstract=None.
    """

    pmid: str | None = None
    title: str | None = None
    abstract: str | None = None
    journal: str | None = None


def _text(el: ET.Element | None) -> str | None:
    """요소의 모든 텍스트(자식 포함)를 모아 trim해 돌려준다(없으면 None).

    AbstractText 안에 <i>/<sup> 같은 인라인 마크업이 섞일 수 있어 itertext로 평탄화한다.
    """
    if el is None:
        return None
    t = "".join(el.itertext()).strip()
    return " ".join(t.split()) or None


def _abstract_text(article: ET.Element) -> str | None:
    """<Article>/<Abstract>/<AbstractText>(다수)를 하나의 초록 문자열로 결합한다.

    구조화 초록은 각 <AbstractText>에 Label(예: BACKGROUND)이 있다 → 'LABEL: 본문'으로
    프리픽스해 줄바꿈 결합. Label이 없으면 본문만. AbstractText가 없으면 None.
    출처: 라이브(구조화 초록 Label 속성) — PubMed DTD AbstractText@Label.
    """
    parts: list[str] = []
    for at in article.findall("./Abstract/AbstractText"):
        body = _text(at)
        if not body:
            continue
        label = at.get("Label")
        parts.append(f"{label}: {body}" if label else body)
    if not parts:
        return None
    return "\n".join(parts)


def _parse_article(pa: ET.Element) -> PubmedArticle:
    """단일 <PubmedArticle> 요소를 PubmedArticle로 파싱한다."""
    pmid = _text(pa.find("./MedlineCitation/PMID"))
    article = pa.find("./MedlineCitation/Article")
    if article is None:
        return PubmedArticle(pmid=pmid)
    journal = _text(article.find("./Journal/Title")) or _text(
        article.find("./Journal/ISOAbbreviation")
    )
    return PubmedArticle(
        pmid=pmid,
        title=_text(article.find("./ArticleTitle")),
        abstract=_abstract_text(article),
        journal=journal,
    )


def parse_abstracts(xml_text: str) -> list[PubmedArticle]:
    """efetch abstract XML 문자열을 PubmedArticle 목록으로 파싱한다.

    <PubmedArticleSet> 안의 <PubmedArticle>* 를 순서대로 변환한다. 없는 PMID는 상류가 빈
    <PubmedArticleSet></PubmedArticleSet>를 주므로 빈 리스트가 된다(라이브 확인).
    XML이 깨졌으면 ET.ParseError가 올라간다(호출부가 매핑).
    출처: 라이브 efetch 응답 구조(PubmedArticleSet/PubmedArticle).
    """
    root = ET.fromstring(xml_text)
    return [_parse_article(pa) for pa in root.findall("./PubmedArticle")]


# ─── 공용 헬퍼 ──────────────────────────────────────────────


def _to_int(value: object) -> int | None:
    """문자열/숫자를 int로 변환한다(불가하면 None). esearch가 count 등을 문자열로 줌."""
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
