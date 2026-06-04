"""E-Gen(국립중앙의료원) 응급의료정보 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`EGEN_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님) → contract.build_*_params가 params에 넣는다. 사전발급 키이고
인터랙티브 OAuth가 아니므로 make_auth_client 없음(airkorea와 동형). 키가 없으면 HTTP 호출
전에 안내 문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

응답은 **XML**이다(arxiv처럼 코어 `get_text`로 raw str을 받아 표준 라이브러리로 파싱).
상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류 등은 봉투 `header.resultCode`(!= "00")로
온다. 그래서 _check_header로 봉투를 먼저 검사해 에러를 매핑한다(airkorea와 동형).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_text
from arcsolve.services import _datagokr
from arcsolve.services.egen import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class EgenSettings(BaseSettings):
    """EGEN_* 환경변수에서 자격증명을 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지).
    """

    model_config = SettingsConfigDict(env_prefix="EGEN_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: EGEN_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)의 "
    "'국립중앙의료원_전국 응급의료기관 정보 조회 서비스'(ErmctInfoInqireService)를 신청해 "
    "서비스키를 발급받아 설정하세요. "
    "(발급: https://www.data.go.kr/data/15000563/openapi.do · "
    "⚠️ Encoding/Decoding 2종 중 **Decoding 키(원문)**를 넣으세요 — 이중 인코딩 방지.)"
)

def _explain(e: UpstreamError) -> str:
    """HTTP 4xx/5xx(드묾 — 보통 200+봉투 에러)를 사람이 읽을 메시지로 매핑한다.

    data.go.kr는 키 오류 등을 HTTP 200 + 봉투(_check_header)로 주는 일이 많지만, 게이트웨이
    레벨 차단은 4xx/5xx + 비-JSON(XML/HTML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = payload.get("returnAuthMsg") or payload.get("resultMsg") or payload.get("message")
    detail = f" {msg}" if msg else ""  # 비-JSON(XML/HTML) 본문은 노출하지 않음
    if e.status in (401, 403):
        return (
            f"인증/권한 오류({e.status}): EGEN_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도를 확인하세요.{detail}"
    return f"E-Gen API 오류 {e.status}:{detail}"


def _check_header(header: c.Header | None) -> str | None:
    """봉투 header.resultCode를 검사한다. 정상("00")이면 None, 아니면 에러 안내 문자열.

    봉투에서 resultCode/resultMsg를 꺼내는 것은 이 서비스가 책임지고(봉투 구조: XML
    `header.resultCode` — parse_header가 cmmMsgHeader도 흡수), 코드→안내 해석은 공유 헬퍼
    (_datagokr.explain_result_code)에 위임한다(canonical 코드표 — 05/10/11/21/33 등 일관 안내).
    출처: https://www.data.go.kr/data/15000563/openapi.do (응답 header.resultCode/resultMsg).
    """
    if header is None or header.resultCode is None:
        return None  # header가 없으면 통과(데이터로 판단)
    return _datagokr.explain_result_code(header.resultCode, header.resultMsg)


def _v(value: str | None) -> str:
    """값 문자열을 표시용으로 정규화한다(결측 ''/None/'-' → '-')."""
    if value is None or value == "" or value == "-":
        return "-"
    return value


def _where(stage1: str, stage2: str | None) -> str:
    """안내용 지역 문자열(STAGE1 + 선택 STAGE2)."""
    return f"{stage1} {stage2}".strip() if stage2 else stage1


def _page_note(page: c.Page) -> str:
    """파싱된 페이지네이션 (totalCount, pageNo, numOfRows)로 '총 N건 · page P' 안내를 만든다."""
    total, page_no, _ = page
    note = f"총 {total if total is not None else '?'}건"
    if page_no is not None:
        note += f" · page {page_no}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    @mcp.tool
    async def egen_realtime_beds(
        stage1: str,
        stage2: str | None = None,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터명)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """응급실 실시간 가용병상정보를 조회한다(GET /getEmrrmRltmUsefulSckbdInfoInqire).

        시도(STAGE1)·시군구(STAGE2)별 응급의료기관의 실시간 가용 병상수(응급실·수술실·각종
        중환자실·입원실)와 장비 가용여부(CT/MRI/조영촬영기/인공호흡기/구급차)를 돌려준다.
        가용수는 정수 문자열, 가용여부는 'Y'/'N'이며 결측은 '-'.

        Args:
            stage1: 시도명(한글, 예: 서울특별시·경기도). 필수.
            stage2: 시군구명(한글, 예: 강남구). 생략 시 시도 전체.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = EgenSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_realtime_beds_params(
            stage1=stage1, service_key=s.service_key, stage2=stage2,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            xml = await get_text(f"{c.BASE_URL}{c.PATH_REALTIME_BEDS}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            header, items, page = c.parse_realtime_beds(xml)
        except ParseError:
            return "응답 파싱 실패: E-Gen이 올바른 XML을 반환하지 않았습니다."

        err = _check_header(header)
        if err:
            return err
        where = _where(stage1, stage2)
        if not items:
            return f"가용병상 데이터 없음. (지역={where})"
        lines = [f"{_page_note(page)} · 지역 {where}"]
        for m in items:
            lines.append(
                f"- [{m.dutyName or m.hpid or '?'}] {m.hvidate or '?'} · "
                f"응급실 {_v(m.hvec)} · 수술실 {_v(m.hvoc)} · 일반중환자 {_v(m.hvicc)} · "
                f"입원실 {_v(m.hvgc)} · CT {_v(m.hvctayn)} · MRI {_v(m.hvmriayn)} · "
                f"인공호흡기 {_v(m.hvventiayn)} · 구급차 {_v(m.hvamyn)}"
                + (f" · ☎ {m.dutyTel3}" if m.dutyTel3 else "")
            )
        return "\n".join(lines)

    @mcp.tool
    async def egen_severe_acceptance(
        stage1: str,
        stage2: str | None = None,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """중증질환자 수용가능정보를 조회한다(GET /getSrsillDissAceptncPosblInfoInqire).

        시도(STAGE1)·시군구(STAGE2)별 응급의료기관이 심근경색·뇌출혈·중증화상 등 중증질환자를
        수용 가능한지(MKioskTy 단말 표시 기준)를 돌려준다. 각 항목은 'Y'(가능)/'N'(불가)/'정보없음'.

        Args:
            stage1: 시도명(한글). 필수.
            stage2: 시군구명(한글). 생략 시 시도 전체.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = EgenSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_severe_acceptance_params(
            stage1=stage1, service_key=s.service_key, stage2=stage2,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            xml = await get_text(f"{c.BASE_URL}{c.PATH_SEVERE_ACCEPTANCE}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            header, items, page = c.parse_severe_acceptance(xml)
        except ParseError:
            return "응답 파싱 실패: E-Gen이 올바른 XML을 반환하지 않았습니다."

        err = _check_header(header)
        if err:
            return err
        where = _where(stage1, stage2)
        if not items:
            return f"수용가능 데이터 없음. (지역={where})"
        lines = [f"{_page_note(page)} · 지역 {where}"]
        for it in items:
            # MKioskTy 슬롯 중 'Y'(수용 가능)인 항목만 추려 표시(가독성). 비면 정보없음 안내.
            available = [k for k, val in sorted(it.mkiosk.items()) if val.upper() == "Y"]
            avail_note = ", ".join(available) if available else "수용 가능 항목 없음/정보없음"
            lines.append(
                f"- [{it.dutyName or it.hpid or '?'}] {it.hvidate or '?'} · 수용가능: {avail_note}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def egen_list(
        stage1: str,
        stage2: str | None = None,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """응급의료기관 목록정보를 조회한다(GET /getEgytListInfoInqire).

        시도(STAGE1)·시군구(STAGE2)별 응급의료기관의 기관명·주소·전화(대표/응급실)·분류·
        위경도를 돌려준다.

        Args:
            stage1: 시도명(한글). 필수.
            stage2: 시군구명(한글). 생략 시 시도 전체.
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        s = EgenSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_list_params(
            stage1=stage1, service_key=s.service_key, stage2=stage2,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            xml = await get_text(f"{c.BASE_URL}{c.PATH_LIST}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            header, items, page = c.parse_list(xml)
        except ParseError:
            return "응답 파싱 실패: E-Gen이 올바른 XML을 반환하지 않았습니다."

        err = _check_header(header)
        if err:
            return err
        where = _where(stage1, stage2)
        if not items:
            return f"응급의료기관 데이터 없음. (지역={where})"
        lines = [f"{_page_note(page)} · 지역 {where}"]
        for h in items:
            tel = h.dutyTel3 or h.dutyTel1
            geo = f" · ({h.wgs84Lat},{h.wgs84Lon})" if h.wgs84Lat and h.wgs84Lon else ""
            lines.append(
                f"- [{h.dutyName or h.hpid or '?'}]"
                + (f" {h.dutyEmclsName}" if h.dutyEmclsName else "")
                + (f" · {h.dutyAddr}" if h.dutyAddr else "")
                + (f" · ☎ {tel}" if tel else "")
                + geo
            )
        return "\n".join(lines)
