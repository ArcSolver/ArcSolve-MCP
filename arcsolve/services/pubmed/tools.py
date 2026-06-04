"""PubMed(NCBI E-utilities) 생의학 문헌 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **선택**(키 없이도 동작). 키(`api_key`)와 식별용 `tool`/`email`은 헤더가 아니라
**쿼리 파라미터**다(OpenAlex와 동형) → 공통 쿼리에 합쳐 넣는다. E-utilities는 도구별로 응답
포맷이 다르다:
  - esearch / esummary → `retmode=json` → 코어 `get_json`(본문 dict)
  - efetch(abstract) → **XML만(JSON 미지원)** → 코어 `get_text`(raw str) + contract.parse_abstracts
인터랙티브 OAuth가 아니므로 make_auth_client 없음(openalex/arxiv/crossref와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json, get_text
from arcsolve.services.pubmed import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class PubMedSettings(BaseSettings):
    """NCBI_* 환경변수에서 (선택) 자격증명을 로드한다.

    - api_key: NCBI API 키(선택). 있으면 쿼리 `api_key=`로 보낸다 → 10 req/s(없으면 3 req/s).
    - tool: 식별용 애플리케이션 이름(선택·권장, 공백 없음). 있으면 쿼리 `tool=`.
    - email: 식별용 연락 이메일(선택·권장). 있으면 쿼리 `email=`.
    출처: NBK25497(api_key·tool·email·레이트리밋 3/10 req/s).
    """

    model_config = SettingsConfigDict(env_prefix="NCBI_", env_file=".env", extra="ignore")
    api_key: str | None = None
    # 기본 tool 식별값(env로 덮어쓸 수 있음) — 공식 etiquette 권장.
    tool: str | None = "arcsolve"
    email: str | None = None


def _auth_params(s: PubMedSettings) -> dict[str, str]:
    """(선택) api_key·tool·email을 쿼리 파라미터 dict로 만든다(없는 값은 생략).

    출처: NBK25497 — api_key/tool/email 모두 쿼리 파라미터(헤더 아님).
    """
    params: dict[str, str] = {}
    if s.api_key:
        params[c.PARAM_API_KEY] = s.api_key
    if s.tool:
        params[c.PARAM_TOOL] = s.tool
    if s.email:
        params[c.PARAM_EMAIL] = s.email
    return params


def _explain(e: UpstreamError) -> str:
    """문서화/관측된 상태코드를 사람이 읽을 메시지로 매핑한다.

    E-utilities는 비-JSON(평문/XML) 본문을 줄 수 있어 dict가 아니면 원문을 노출하지 않는다.
    레이트리밋 초과(키 없이 3 req/s 초과)는 429다.
    출처: NBK25497(레이트리밋 3/10 req/s, 초과 시 에러).
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = payload.get("error") or payload.get("message")
    detail = f" {str(msg).strip()}" if msg else ""  # 비-JSON 본문은 노출하지 않음
    if e.status == 400:
        return f"요청 오류(400): term/id/retmax/retstart/sort를 확인하세요.{detail}"
    if e.status == 414:
        return "요청 URL이 너무 깁니다(414): id 개수를 줄이거나 분할 요청하세요."
    if e.status == 429:
        return (
            "요청 한도 초과(429): 키 없이는 초당 3건까지입니다. 잠시 후 재시도하세요. "
            f"NCBI_API_KEY를 쓰면 초당 10건으로 늘어납니다.{detail}"
        )
    return f"PubMed E-utilities 오류 {e.status}:{detail}"


def _author_summary(authors: list[c.SummaryAuthor]) -> str:
    """authors 배열에서 '첫 저자 외 N명' 형태의 짧은 요약을 만든다."""
    if not authors:
        return "(저자 정보 없음)"
    name = authors[0].name or "(이름 없음)"
    extra = len(authors) - 1
    return f"{name} 외 {extra}명" if extra > 0 else name


def _summary_line(a: c.ArticleSummary) -> str:
    """요약 1줄: `- [PMID] (pubdate) title — 첫 저자 · source`."""
    pmid = a.uid or "?"
    date = a.pubdate or "?"
    src = f" · {a.source}" if a.source else ""
    return f"- [{pmid}] ({date}) {a.title or '(제목 없음)'} — {_author_summary(a.authors)}{src}"


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def pubmed_search(
        query: str,
        retmax: int = c.DEFAULT_RETMAX,
        retstart: int = 0,
        sort: str | None = None,
    ) -> str:
        """PubMed에서 생의학 문헌을 검색해 PMID 목록을 받는다(GET esearch.fcgi, db=pubmed).

        Args:
            query: Entrez 검색식(`term`)을 그대로 전달한다. 필드 태그를 붙일 수 있다 —
                `[ti]`(제목) `[au]`(저자) `[mesh]`(MeSH) `[dp]`(출판일) 등. 불리언
                `AND`/`OR`/`NOT`로 결합. 예: `crispr AND cas9[ti]`, `covid-19[mesh]`.
            retmax: 가져올 PMID 개수. 기본 20, 0..10000.
            retstart: 결과 시작 오프셋(0부터). 페이지네이션용.
            sort: 정렬 `relevance`(Best Match·기본)/`pub_date`/`Author`/`JournalName`.
        """
        s = PubMedSettings()
        try:
            params = c.build_search_params(
                term=query, retmax=retmax, retstart=retstart, sort=sort
            )
        except ValueError as e:  # 범위/열거 위반은 HTTP 전에 막힌다
            return str(e)
        params.update(_auth_params(s))

        try:
            body = await get_json(f"{c.BASE_URL}{c.ESEARCH}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        err = c.search_error(body)
        if err:
            return f"PubMed 검색 오류: {err}"
        result = c.parse_esearch(body)
        note = f"총 {result.count if result.count is not None else '?'}건"
        if result.retstart:
            note += f" · offset {result.retstart}"
        if not result.idlist:
            return f"검색 결과 없음. ({note})"
        ids = ", ".join(result.idlist)
        return f"{note}\nPMID: {ids}"

    @mcp.tool
    async def pubmed_get_summary(ids: str) -> str:
        """PMID로 논문 요약(제목·저자·저널·날짜·DOI)을 조회한다(GET esummary.fcgi, retmode=json).

        Args:
            ids: 콤마로 구분한 PMID 목록(예: `31452104,23092060`). 1회 최대 200개.
                없는 PMID는 조용히 건너뛰지 않고 '(요약 없음)'으로 표시한다.
        """
        s = PubMedSettings()
        try:
            params = c.build_summary_params(ids=ids)
        except ValueError as e:
            return str(e)
        params.update(_auth_params(s))

        try:
            body = await get_json(f"{c.BASE_URL}{c.ESUMMARY}", params=params)
        except UpstreamError as e:
            return _explain(e)

        if not isinstance(body, dict):
            return f"응답: {body}"
        summaries = c.parse_esummary(body)
        if not summaries:
            return "요약 없음. PMID를 확인하세요."
        if len(summaries) == 1:
            a = summaries[0]
            if not a.title:
                return f"[{a.uid or '?'}] (요약 없음) — PMID를 확인하세요."
            lines = [
                f"[{a.uid or '?'}] ({a.pubdate or '?'}) {a.title}",
                f"- 저자: {_author_summary(a.authors)}",
            ]
            journal = a.fulljournalname or a.source
            if journal:
                vip = "".join(
                    part
                    for part in [
                        f" {a.volume}" if a.volume else "",
                        f"({a.issue})" if a.issue else "",
                        f":{a.pages}" if a.pages else "",
                    ]
                )
                lines.append(f"- 저널: {journal}{vip}")
            if a.doi:
                lines.append(f"- DOI: {a.doi}")
            return "\n".join(lines)
        return f"총 {len(summaries)}건\n" + "\n".join(_summary_line(a) for a in summaries)

    @mcp.tool
    async def pubmed_fetch_abstract(ids: str) -> str:
        """PMID로 초록(abstract) 본문을 가져온다(GET efetch.fcgi, rettype=abstract&retmode=xml).

        efetch는 JSON을 지원하지 않아 XML로 받아 표준 라이브러리로 파싱한다. 구조화 초록
        (BACKGROUND/METHODS 등)은 라벨을 붙여 보여준다.

        Args:
            ids: 콤마로 구분한 PMID 목록(예: `31452104,23092060`). 1회 최대 200개.
                초록이 없는 레코드는 '(초록 없음)'으로 표시한다.
        """
        s = PubMedSettings()
        try:
            params = c.build_fetch_params(ids=ids)
        except ValueError as e:
            return str(e)
        params.update(_auth_params(s))

        try:
            xml = await get_text(f"{c.BASE_URL}{c.EFETCH}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            articles = c.parse_abstracts(xml)
        except ParseError:
            return "응답 파싱 실패: PubMed가 올바른 XML을 반환하지 않았습니다."

        if not articles:
            return "결과 없음. PMID를 확인하세요."
        blocks: list[str] = []
        for art in articles:
            header = f"[{art.pmid or '?'}] {art.title or '(제목 없음)'}"
            if art.journal:
                header += f"\n- 저널: {art.journal}"
            body = art.abstract or "(초록 없음)"
            blocks.append(f"{header}\n- 초록: {body}")
        return "\n\n".join(blocks)
