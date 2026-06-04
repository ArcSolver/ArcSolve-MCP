"""전기차 충전소(한국환경공단) 정보·실시간 상태 읽기 MCP 도구 + 런타임 배선.

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`EV_CHARGER_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님) → contract.build_*_params가 params에 넣는다. 사전발급 키이고
인터랙티브 OAuth가 아니므로 make_auth_client 없음(airkorea·egen과 동형). 키가 없으면 HTTP
호출 전에 안내 문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

⚠️ 실시간 상태 지연: getChargerStatus는 "실시간"이지만 상류가 약 5분 주기로 갱신한다 → 결과는
항상 수 분 지연된 캐시 스냅샷이다(`statUpdDt`로 갱신시각 확인).

응답은 **XML**이다(egen/arxiv처럼 코어 `get_text`로 raw str을 받아 표준 라이브러리로 파싱).
상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류 등은 봉투 `header.resultCode`(!= "00")로
온다(게이트웨이 차단은 `cmmMsgHeader`로). 그래서 _check_header로 봉투를 먼저 검사해 매핑한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_text
from arcsolve.services import _datagokr
from arcsolve.services.ev_charger import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class EvChargerSettings(BaseSettings):
    """EV_CHARGER_* 환경변수에서 자격증명을 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지).
    """

    model_config = SettingsConfigDict(env_prefix="EV_CHARGER_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: EV_CHARGER_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)의 "
    "'한국환경공단_전기자동차 충전소 정보' OpenAPI(EvCharger)를 신청해 서비스키를 발급받아 "
    "설정하세요. (발급: https://www.data.go.kr/data/15076352/openapi.do · "
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
            f"인증/권한 오류({e.status}): EV_CHARGER_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도를 확인하세요.{detail}"
    return f"전기차 충전소 API 오류 {e.status}:{detail}"


def _check_header(header: c.Header | None) -> str | None:
    """봉투 header.resultCode를 검사한다. 정상("00")이면 None, 아니면 에러 안내 문자열.

    봉투에서 resultCode/resultMsg를 꺼내는 것은 이 서비스가 책임지고(봉투 구조: XML
    `header.resultCode` — parse_header가 cmmMsgHeader도 흡수), 코드→안내 해석은 공유 헬퍼
    (_datagokr.explain_result_code)에 위임한다(canonical 코드표 — 05/10/11/21/33 등 일관 안내).
    출처: https://www.data.go.kr/data/15076352/openapi.do (응답 header.resultCode/resultMsg).
    """
    if header is None or header.resultCode is None:
        return None  # header가 없으면 통과(데이터로 판단)
    return _datagokr.explain_result_code(header.resultCode, header.resultMsg)


def _v(value: str | None) -> str:
    """값 문자열을 표시용으로 정규화한다(결측 ''/None/'-' → '-')."""
    if value is None or value == "" or value == "-":
        return "-"
    return value


def _stat_label(code: str | None) -> str:
    """충전기 상태 코드를 '코드(한글)'로 표시한다(미상 코드는 코드만)."""
    if code is None or code == "":
        return "-"
    label = c.STAT_LABELS.get(code)
    return f"{code}({label})" if label else code


def _chger_type_label(code: str | None) -> str:
    """충전기 타입 코드를 '코드(한글)'로 표시한다(미상 코드는 코드만 보존)."""
    if code is None or code == "":
        return "-"
    label = c.CHGER_TYPE_LABELS.get(code)
    return f"{code}({label})" if label else code


def _where(zcode: str | None, zscode: str | None) -> str:
    """안내용 지역 문자열(zcode 시도 + 선택 zscode 시군구). 둘 다 없으면 '전국'."""
    if zcode and zscode:
        return f"zcode={zcode}·zscode={zscode}"
    if zcode:
        return f"zcode={zcode}"
    if zscode:
        return f"zscode={zscode}"
    return "전국"


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
    async def ev_charger_status(
        zcode: str | None = None,
        zscode: str | None = None,
        period: int = c.DEFAULT_PERIOD,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터명)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """충전기 실시간 상태를 조회한다(GET /getChargerStatus).

        충전기별 상태(충전중/충전대기/통신이상/운영중지/점검중/상태미확인)와 상태갱신일시를
        돌려준다. 지역코드로 필터할 수 있다.

        ⚠️ "실시간"이지만 상류가 **약 5분 주기**로 갱신한다 → 결과는 수 분 지연된 캐시
        스냅샷이며 `statUpdDt`(상태갱신일시)로 실제 시각을 확인한다.

        Args:
            zcode: 시도 지역코드(행정구역코드 앞 2자리, 예: 11=서울). 생략 시 전국.
            zscode: 시군구 지역코드. 생략 시 zcode 시도 전체.
            period: 상태갱신 조회범위(분). 기본 5(상태 갱신 주기), 최소 1·최대 10.
            numOfRows: 페이지 크기(기본 100, 최소 10·최대 9999).
            pageNo: 페이지 번호(기본 1).
        """
        s = EvChargerSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_charger_status_params(
            service_key=s.service_key, zcode=zcode, zscode=zscode,
            period=period, num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            xml = await get_text(f"{c.BASE_URL}{c.PATH_CHARGER_STATUS}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            header, items, page = c.parse_charger_status(xml)
        except ParseError:
            return "응답 파싱 실패: 전기차 충전소 API가 올바른 XML을 반환하지 않았습니다."

        err = _check_header(header)
        if err:
            return err
        where = _where(zcode, zscode)
        if not items:
            return f"충전기 상태 데이터 없음. (지역={where})"
        lines = [f"{_page_note(page)} · 지역 {where} · ⚠️ 약 5분 지연(캐시 스냅샷)"]
        for it in items:
            lines.append(
                f"- [{it.statId or '?'}/{it.chgerId or '?'}] 상태 {_stat_label(it.stat)} · "
                f"갱신 {_v(it.statUpdDt)}"
                + (f" · 기관 {it.busiId}" if it.busiId else "")
            )
        return "\n".join(lines)

    @mcp.tool
    async def ev_charger_info(
        zcode: str | None = None,
        zscode: str | None = None,
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터명)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """충전소 정보를 조회한다(GET /getChargerInfo).

        충전소·충전기의 위치(주소·위경도)·충전기 타입(완속/급속/DC콤보 등 코드)·운영기관·
        이용가능시간을 돌려준다. 지역코드로 필터할 수 있다.

        Args:
            zcode: 시도 지역코드(행정구역코드 앞 2자리, 예: 11=서울). 생략 시 전국.
            zscode: 시군구 지역코드. 생략 시 zcode 시도 전체.
            numOfRows: 페이지 크기(기본 100, 최소 10·최대 9999).
            pageNo: 페이지 번호(기본 1).
        """
        s = EvChargerSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_charger_info_params(
            service_key=s.service_key, zcode=zcode, zscode=zscode,
            num_of_rows=numOfRows, page_no=pageNo,
        )
        try:
            xml = await get_text(f"{c.BASE_URL}{c.PATH_CHARGER_INFO}", params=params)
        except UpstreamError as e:
            return _explain(e)
        try:
            header, items, page = c.parse_charger_info(xml)
        except ParseError:
            return "응답 파싱 실패: 전기차 충전소 API가 올바른 XML을 반환하지 않았습니다."

        err = _check_header(header)
        if err:
            return err
        where = _where(zcode, zscode)
        if not items:
            return f"충전소 정보 데이터 없음. (지역={where})"
        lines = [f"{_page_note(page)} · 지역 {where}"]
        for ch in items:
            geo = f" · ({ch.lat},{ch.lng})" if ch.lat and ch.lng else ""
            lines.append(
                f"- [{ch.statNm or ch.statId or '?'}/{ch.chgerId or '?'}] "
                f"타입 {_chger_type_label(ch.chgerType)}"
                + (f" · {ch.addr}" if ch.addr else "")
                + (f" {ch.location}" if ch.location else "")
                + geo
                + (f" · 운영 {ch.busiNm}" if ch.busiNm else "")
                + (f" · 이용시간 {ch.useTime}" if ch.useTime else "")
            )
        return "\n".join(lines)
