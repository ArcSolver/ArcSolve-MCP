"""KOTSA 전국 주차정보 읽기 MCP 도구 + 런타임 배선(자격증명·요청 조립·에러 매핑).

contract.py의 계약을 실제 MCP 도구로 노출하는 얇은 층. 전부 GET·읽기다.

인증은 **서비스키 필수**(`PARKING_SERVICE_KEY`) — OAuth가 아니라 **쿼리 파라미터 `serviceKey`**다
(헤더 아님) → contract.build_params가 params에 넣는다. 사전발급 키이고 인터랙티브 OAuth가
아니므로 make_auth_client 없음(airkorea/tago/egen과 동형). 키가 없으면 HTTP 호출 전에 안내
문자열을 반환한다.

⚠️ data.go.kr 서비스키 함정: 키는 Encoding/Decoding 2종으로 발급된다. httpx가 쿼리 파라미터를
자동 URL-인코딩하므로 **Decoding 키(원문)**를 그대로 settings로 받아 넣는다(이중 인코딩 방지).

⚠️ 실시간 잔여면 커버리지 한계: `parking_realtime`의 잔여면(현재 주차가능 구획 수)은 **시스템에
연동된 일부 주차장만** 제공된다(공식 안내: 실시간 정보는 시설정보보다 데이터 수가 적음). 대다수
주차장은 정적 시설/운영정보만 있다 — 과장 금지.

상류는 정상이어도 **HTTP 200**으로 응답하고, 키 오류·무데이터는 봉투 `resultCode`(!= "00")로
온다. B553881은 결과코드가 **최상위**에 실릴 수 있어 그 위치를 우선 검사하고, 게이트웨이 키
차단(`cmmMsgHeader.returnReasonCode`)을 보조 검사한다. 항목 배열은 표준 래핑이 아니라
**오퍼레이션명 키 아래**에 실린다(contract.normalize_items가 흡수).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from arcsolve.http import UpstreamError, get_json
from arcsolve.services.parking import contract as c

if TYPE_CHECKING:
    from fastmcp import FastMCP  # 타입힌트 전용 — 런타임 fastmcp import 회피


class ParkingSettings(BaseSettings):
    """PARKING_* 환경변수에서 서비스키를 로드한다.

    - service_key: data.go.kr 발급 서비스키(필수). **Decoding 키(원문)**를 넣는다
      (httpx 자동 인코딩으로 인한 이중 인코딩 방지). 단일 키로 3개 오퍼레이션 전부 커버한다.
    """

    model_config = SettingsConfigDict(env_prefix="PARKING_", env_file=".env", extra="ignore")
    service_key: str | None = None


_MISSING_KEY = (
    "설정 오류: PARKING_SERVICE_KEY가 없습니다. 공공데이터포털(data.go.kr)에서 한국교통안전공단 "
    "'주차정보 제공 API'(15099883 — 시설정보/운영정보/실시간정보)를 활용 신청해 서비스키를 "
    "발급받아 설정하세요. 단일 키로 3개 오퍼레이션 전부 커버됩니다. "
    "(발급: https://www.data.go.kr/data/15099883/openapi.do · "
    "⚠️ Encoding/Decoding 2종 중 **Decoding 키(원문)**를 넣으세요 — 이중 인코딩 방지.)"
)

# data.go.kr 공통 에러코드(서비스키/트래픽/무데이터 등) → 사람이 읽을 안내.
# 출처: 공공데이터포털 OpenAPI 공통 에러코드 규약 + 응답 resultCode/resultMsg.
_RESULT_CODE_HINTS = {
    "01": "어플리케이션 에러(01): 잠시 후 재시도하세요.",
    "02": "데이터베이스 에러(02): 잠시 후 재시도하세요.",
    "03": "데이터 없음(03): 해당 조건의 주차장 데이터가 없습니다.",
    "04": "HTTP 에러(04).",
    "05": "서비스 연결 실패(05): 잠시 후 재시도하세요.",
    "10": "잘못된 요청 파라미터(10): 입력값(페이지·건수)을 확인하세요.",
    "11": "필수 요청 파라미터 누락(11): serviceKey/format 등 필수값을 확인하세요.",
    "12": "폐기된 서비스(12): 해당 OpenAPI는 더 이상 제공되지 않습니다.",
    "20": "서비스 접근 거부(20): 서비스키 권한/IP 설정을 확인하세요.",
    "21": "일시적 사용 중지(21): 잠시 후 재시도하세요.",
    "22": "서비스 요청 제한 초과(22): 일일 트래픽 한도(개발계정)를 초과했습니다.",
    "30": (
        "등록되지 않은 서비스키(30): PARKING_SERVICE_KEY를 확인하세요. "
        "⚠️ Encoding이 아니라 **Decoding 키(원문)**를 넣어야 합니다(이중 인코딩 방지)."
    ),
    "31": "기한 만료 서비스키(31): 활용기간이 만료되었습니다. data.go.kr에서 연장하세요.",
    "32": "등록되지 않은 IP(32): 서비스키에 허용 IP를 등록하세요.",
    "99": "기타 에러(99).",
}


def _explain_http(e: UpstreamError) -> str:
    """HTTP 4xx/5xx(게이트웨이 차단 등)를 사람이 읽을 메시지로 매핑한다.

    data.go.kr는 키 오류 등을 HTTP 200 + 봉투로 주는 일이 많지만, 게이트웨이 레벨 차단은
    4xx/5xx + 비-JSON(XML/HTML) 본문일 수 있다. dict가 아니면 원문 노출을 막는다.
    """
    payload = e.payload if isinstance(e.payload, dict) else None
    msg = None
    if payload:
        msg = (
            payload.get("returnAuthMsg")
            or payload.get("resultMsg")
            or payload.get("returnReasonCode")
            or payload.get("message")
        )
    detail = f" {msg}" if msg else ""  # 비-JSON(XML/HTML) 본문은 노출하지 않음
    if e.status in (401, 403):
        return (
            f"인증/권한 오류({e.status}): PARKING_SERVICE_KEY(Decoding 키)와 서비스 권한을 "
            f"확인하세요.{detail}"
        )
    if e.status == 429:
        return f"요청 한도 초과(429): 일일 트래픽 한도를 확인하세요.{detail}"
    return f"주차정보 API 오류 {e.status}:{detail}"


def _hint_for_code(code: str, msg: str) -> str:
    hint = _RESULT_CODE_HINTS.get(code)
    if hint:
        return f"{hint}{(' (' + msg + ')') if msg else ''}"
    return f"주차정보 응답 오류(resultCode={code}){(': ' + msg) if msg else ''}"


def _check_envelope(body: dict, env: c.Envelope) -> str | None:
    """봉투를 검사한다. 정상("00")/없음이면 None, 아니면 에러 안내 문자열.

    1) 최상위 `resultCode`(B553881 봉투) 우선 검사.
    2) 게이트웨이 키 차단은 `cmmMsgHeader.returnReasonCode`(+ returnAuthMsg)로 올 수 있어 보조 검사
       (표준 data.go.kr 게이트웨이 규약 — 최상위/response/OpenAPI_ServiceResponse 아래 모두 탐색).
    출처: 위 페이지 응답 resultCode/resultMsg + data.go.kr 게이트웨이 cmmMsgHeader 규약.
    """
    if env.resultCode is not None:
        if env.resultCode != c.RESULT_CODE_OK:
            return _hint_for_code(env.resultCode, env.resultMsg or "")
        return None
    # resultCode가 없을 때만 cmmMsgHeader(게이트웨이 차단) 보조 검사.
    cmm = body.get("cmmMsgHeader") if isinstance(body, dict) else None
    if not isinstance(cmm, dict):
        for wrapper_key in ("response", "OpenAPI_ServiceResponse"):
            wrapper = body.get(wrapper_key) if isinstance(body, dict) else None
            if isinstance(wrapper, dict) and isinstance(wrapper.get("cmmMsgHeader"), dict):
                cmm = wrapper["cmmMsgHeader"]
                break
    if isinstance(cmm, dict):
        code = cmm.get("returnReasonCode")
        amsg = cmm.get("returnAuthMsg") or cmm.get("errMsg") or ""
        if code is not None and str(code) not in ("", c.RESULT_CODE_OK):
            return _hint_for_code(str(code), str(amsg))
    return None


def _unwrap(body: Any) -> dict | None:
    """상류 본문을 봉투 dict로 정규화한다.

    B553881은 보통 최상위 dict에 결과코드·오퍼레이션명 키를 둔다. 일부 게이트웨이가
    `response`로 한 번 더 감쌀 수 있어 그 안쪽도 흡수한다(둘 다 dict면 최상위 우선).
    """
    if not isinstance(body, dict):
        return None
    inner = body.get("response")
    # response 래핑이 있고 최상위에 결과코드/오퍼레이션 키가 없으면 inner 사용.
    if isinstance(inner, dict) and "resultCode" not in body:
        return inner
    return body


def _v(value: str | None) -> str:
    """표시용 정규화(None/빈 문자열 → '-')."""
    if value is None or value == "":
        return "-"
    return value


def _page_note(env: c.Envelope) -> str:
    """봉투 페이지네이션으로 '총 N건 · page P' 안내 문자열을 만든다."""
    total = env.totalCount if env.totalCount is not None else "?"
    note = f"총 {total}건"
    if env.pageNo is not None:
        note += f" · page {env.pageNo}"
    return note


def register(mcp: FastMCP) -> None:
    """이 서비스의 도구를 서버에 등록한다."""

    async def _fetch(op: str, num_of_rows: int, page_no: int) -> tuple[dict, c.Envelope] | str:
        """공통: 서비스키 확인 → GET → 봉투 파싱 + 에러 매핑.

        에러면 안내 문자열, 정상이면 (정규화된 본문 dict, Envelope)을 돌려준다.
        """
        s = ParkingSettings()
        if not s.service_key:
            return _MISSING_KEY
        params = c.build_params(
            service_key=s.service_key, num_of_rows=num_of_rows, page_no=page_no
        )
        url = f"{c.BASE_URL}/{op}"
        try:
            body = await get_json(url, params=params)
        except UpstreamError as e:
            return _explain_http(e)
        if not isinstance(body, dict):
            return f"응답: {body}"
        inner = _unwrap(body)
        inner = inner if inner is not None else body
        env = c.Envelope.model_validate(inner)
        err = _check_envelope(inner, env)
        if err:
            return err
        return inner, env

    @mcp.tool
    async def parking_search(
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803 (공식 파라미터 의미)
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """전국 주차장 시설정보를 조회한다(GET /B553881/Parking/PrkSttusInfo).

        주차정보시스템에 수집된 전국 주차장의 **정적 시설정보**(주차장명·도로명주소·위경도·총
        주차구획 수)를 페이지 단위로 돌려준다. 각 주차장은 **주차장관리번호 `prk_center_id`를
        PK**로 가진다 — `parking_operation`/`parking_realtime`와 이 PK로 연결된다.

        참고: 이 API는 주차장관리번호 등 개별 필터 입력 없이 **전국 목록을 페이지로** 받는다.
        특정 주차장을 찾으려면 `numOfRows`/`pageNo`로 페이지를 넘기며 조회한다.

        Args:
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        res = await _fetch(c.OP_FACILITY, numOfRows, pageNo)
        if isinstance(res, str):
            return res
        inner, env = res
        rows = c.normalize_items(inner, c.OP_FACILITY)
        if not rows:
            return f"주차장 시설정보 없음. (page={pageNo})"
        lots = [c.Facility.model_validate(r) for r in rows]
        lines = [f"{_page_note(env)} · 주차장 시설정보"]
        for f in lots:
            geo = ""
            if f.prk_plce_entrc_la and f.prk_plce_entrc_lo:
                geo = f" · ({f.prk_plce_entrc_la}, {f.prk_plce_entrc_lo})"
            cap = f" · 총 {f.prk_cmprt_co}면" if f.prk_cmprt_co else ""
            addr = f" — {_v(f.prk_plce_adres)}" if f.prk_plce_adres else ""
            lines.append(
                f"- [{_v(f.prk_plce_nm)}] PK={_v(f.prk_center_id)}{cap}{geo}{addr}"
            )
        return "\n".join(lines)

    @mcp.tool
    async def parking_operation(
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """전국 주차장 운영정보를 조회한다(GET /B553881/Parking/PrkOprInfo).

        주차장별 **운영시간·요금 체계**(운영 시작/종료 시각, 기본 무료회차 시간, 기본 시간·요금,
        추가 단위시간·요금)를 PK(`prk_center_id`)와 함께 페이지 단위로 돌려준다.

        ⚠️ 공식 안내상 **운영정보는 시설정보보다 데이터 수가 적다**(연동·등록된 주차장 한정).
        시설정보(`parking_search`)에 있어도 운영정보가 없을 수 있다.

        Args:
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        res = await _fetch(c.OP_OPERATION, numOfRows, pageNo)
        if isinstance(res, str):
            return res
        inner, env = res
        rows = c.normalize_items(inner, c.OP_OPERATION)
        if not rows:
            return f"주차장 운영정보 없음(연동 주차장 한정). (page={pageNo})"
        ops = [c.Operation.model_validate(r) for r in rows]
        lines = [f"{_page_note(env)} · 주차장 운영정보(요금·운영시간)"]
        for o in ops:
            hours = ""
            if o.opertn_start_time or o.opertn_end_time:
                hours = f" · 운영 {_v(o.opertn_start_time)}~{_v(o.opertn_end_time)}"
            fee = ""
            if o.parking_chrge_bs_chrg:
                base = f"기본 {o.parking_chrge_bs_time or '?'}분 {o.parking_chrge_bs_chrg}원"
                add = ""
                if o.parking_chrge_adit_unit_chrge:
                    add = (
                        f", 추가 {o.parking_chrge_adit_unit_time or '?'}분당 "
                        f"{o.parking_chrge_adit_unit_chrge}원"
                    )
                fee = f" · {base}{add}"
            free = f" · 무료회차 {o.opertn_bs_free_time}분" if o.opertn_bs_free_time else ""
            lines.append(f"- PK={_v(o.prk_center_id)}{hours}{fee}{free}")
        return "\n".join(lines)

    @mcp.tool
    async def parking_realtime(
        numOfRows: int = c.DEFAULT_NUM_OF_ROWS,  # noqa: N803
        pageNo: int = c.DEFAULT_PAGE_NO,  # noqa: N803
    ) -> str:
        """전국 주차장 실시간 잔여 주차면을 조회한다(GET /B553881/Parking/PrkRealtimeInfo). ⭐

        시스템에 **연동된 주차장**의 현재 주차가능 구획 수(잔여면)와 주차가능 총 구획 수를
        PK(`prk_center_id`)와 함께 페이지 단위로 돌려준다.

        ⚠️ **실시간 잔여면 제공은 연동 주차장 한정입니다.** 공식 안내상 실시간 정보는 시설정보보다
        데이터 수가 훨씬 적고, 전국 대다수 주차장은 정적 시설정보만 있습니다(이 도구가 비어 있어도
        해당 주차장에 실시간 연동이 없다는 뜻이며 오류가 아닙니다). 과장된 커버리지를 기대하지 마세요.

        Args:
            numOfRows: 페이지 크기(기본 100).
            pageNo: 페이지 번호(기본 1).
        """
        res = await _fetch(c.OP_REALTIME, numOfRows, pageNo)
        if isinstance(res, str):
            return res
        inner, env = res
        rows = c.normalize_items(inner, c.OP_REALTIME)
        if not rows:
            return (
                "실시간 잔여면 데이터 없음. ⚠️ 실시간 잔여면은 연동된 일부 주차장만 제공됩니다 "
                f"— 데이터 없음은 정상일 수 있습니다. (page={pageNo})"
            )
        rts = [c.Realtime.model_validate(r) for r in rows]
        lines = [
            f"{_page_note(env)} · 실시간 잔여 주차면(⚠️ 연동 주차장 한정)"
        ]
        for r in rts:
            avail = _v(r.pkfc_Available_ParkingLots_total)
            total = r.pkfc_ParkingLots_total
            of = f"/{total}" if total else ""
            lines.append(f"- PK={_v(r.prk_center_id)} · 잔여 {avail}{of}면")
        return "\n".join(lines)
