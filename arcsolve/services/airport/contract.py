"""인천국제공항공사(IIAC) 여객편 운항현황 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, 응답 봉투/항목 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. 인천국제공항공사(기관코드 **B551177**)의 **여객편 운항현황 상세조회**
서비스(`StatusOfPassengerFlightsDeOdp`)로 도착(`getPassengerArrivalsDeOdp`)·출발
(`getPassengerDeparturesDeOdp`) 두 오퍼레이션을 노출한다. 인증은 OAuth가 아니라 **쿼리
파라미터 `serviceKey`**다(헤더 아님). 응답은 기본 XML이라 **`type=json`을 명시**한다
(⚠️ data.go.kr 공통 키는 보통 `_type`이지만, 인천공항 운항현황은 파라미터명이 **`type`**다 —
실호출로 교차확인). 페이지네이션/건수는 응답 **본문**(`response.body.totalCount/pageNo/
numOfRows`)에 실린다.

⚠️ data.go.kr 서비스키 함정(airkorea/egen/tago 동일): 키는 **Encoding/Decoding 2종**으로
발급된다. httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를
넣어 이중 인코딩을 피한다.

⚠️ items 봉투 quirk: 이 서비스는 다른 data.go.kr 서비스(`items.item`로 한 단계 더 싸는 TAGO/
airkorea)와 달리 `response.body.items`가 **곧장 항목 리스트**다(실호출 교차확인:
`body.get('items', [])` → 단일 객체면 그대로 dict). 결과가 1건이면 **단일 객체**, 0건이면
빈 리스트/빈 문자열일 수 있다. `normalize_items`가 `item` 중첩·직접 리스트·단일 객체·빈
문자열을 **모두 흡수**한다.

출처(공식 — data.go.kr · 인천국제공항공사 B551177):
  - 항공기 운항 현황 상세 조회(여객편 운항현황 상세조회): https://www.data.go.kr/data/15140153/openapi.do
      · StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp(여객편 도착현황 상세조회)
      · StatusOfPassengerFlightsDeOdp/getPassengerDeparturesDeOdp(여객편 출발현황 상세조회)
  엔드포인트·파라미터·필드명은 다수 외부 구현의 실호출로 교차확인(아래 각 요소 주석 참조).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from arcsolve.services._datagokr import clamp_paging

# ─── base URL / 서비스 경로 상수 ────────────────────────────
# 인천국제공항공사 기관코드 B551177. 출처: data.go.kr 15140153 + 다수 외부 구현 실호출 URL
#   (예: http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDeOdp/getPassengerArrivalsDeOdp).
BASE_URL = "https://apis.data.go.kr/B551177"

# 여객편 운항현황 상세조회 서비스(엔드포인트 그룹) 경로.
SERVICE_PASSENGER_FLIGHTS = "/StatusOfPassengerFlightsDeOdp"

# ─── 오퍼레이션 경로 상수 ───────────────────────────────────
# 출처: 15140153 상세기능 + 외부 구현 실호출 URL.
OP_ARRIVALS = "/getPassengerArrivalsDeOdp"  # 여객편 도착현황 상세조회
OP_DEPARTURES = "/getPassengerDeparturesDeOdp"  # 여객편 출발현황 상세조회


# ─── 쿼리 파라미터명(공식) ──────────────────────────────────
# 출처: 15140153 요청변수 + 외부 구현 실호출 params.
PARAM_SERVICE_KEY = "serviceKey"
PARAM_TYPE = "type"  # ⚠️ 인천공항은 `_type`이 아니라 `type` (실호출 교차확인)
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_PAGE_NO = "pageNo"
PARAM_SEARCH_DAY = "searchday"  # 조회일자 YYYYMMDD(미지정 시 상류 기본=당일)
PARAM_FROM_TIME = "from_time"  # 조회 시작시각 HHMM(예: 0000)
PARAM_TO_TIME = "to_time"  # 조회 종료시각 HHMM(예: 2400)
PARAM_AIRPORT_CODE = "airport_code"  # 출발지/도착지 공항코드(IATA, 선택 필터)
PARAM_FLIGHT_ID = "flight_id"  # 편명 필터(선택)
PARAM_LANG = "lang"  # 언어구분 K(국문)/E(영문) 등

# `type=json`을 명시하지 않으면 상류가 기본 XML을 줘 get_json이 파싱하지 못한다.
TYPE_JSON = "json"

# 언어 기본값. 출처: 외부 구현(lang=K 국문). E=영문.
LANG_KOREAN = "K"

# 공통 페이지네이션 기본값. 출처: 외부 구현(numOfRows 대량 수집은 999, 기본은 10).
DEFAULT_NUM_OF_ROWS = 100
DEFAULT_PAGE_NO = 1
# numOfRows/pageNo 안전 범위.
# TODO(provenance): numOfRows 상한이 상세 페이지에 인라인 명시되지 않아(외부 구현은 999까지 관측),
#   data.go.kr 게이트웨이 통용 상한 9999를 보수적 상한으로 둔다(위반 시 결과코드 10 방지). 하한 1.
MAX_NUM_OF_ROWS = 9999
MIN_NUM_OF_ROWS = 1

# 하루 전체를 덮는 시간 범위 기본값(HHMM). 출처: 외부 구현(from_time=0000, to_time=2400).
DEFAULT_FROM_TIME = "0000"
DEFAULT_TO_TIME = "2400"

# 정상 응답 결과코드. 출처: data.go.kr 공통 OpenAPI 에러코드 규약 + 응답 header.
RESULT_CODE_OK = "00"

# terminalid 코드 → 표시명. 상류는 표시명이 아니라 코드(P01/P02/P03)를 준다.
#   P01=제1여객터미널(T1) · P02=탑승동(concourse) · P03=제2여객터미널(T2).
# 출처: 외부 구현(eyjs/convention C# MapTerminal: P01→T1, P02→탑승동, P03→T2;
#   airscreen iOS Swift: 도착/출발 필터가 P01/P02/P03로 분기).
TERMINAL_NAMES = {
    "P01": "T1",
    "P02": "탑승동",
    "P03": "T2",
}


def _base(service_key: str) -> dict[str, str | int]:
    """모든 운항현황 요청의 공통 베이스 파라미터(serviceKey·type=json)."""
    return {PARAM_SERVICE_KEY: service_key, PARAM_TYPE: TYPE_JSON}


def build_flight_params(
    *,
    service_key: str,
    search_day: str | None = None,
    from_time: str = DEFAULT_FROM_TIME,
    to_time: str = DEFAULT_TO_TIME,
    airport_code: str | None = None,
    flight_id: str | None = None,
    lang: str = LANG_KOREAN,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """여객편 출/도착 운항현황 쿼리스트링(도착·출발 동형 파라미터).

    도착(getPassengerArrivalsDeOdp)·출발(getPassengerDeparturesDeOdp)이 같은 파라미터를 쓴다.
    search_day(YYYYMMDD) 미지정 시 상류 기본(당일). from_time/to_time은 HHMM.
    airport_code/flight_id는 선택 필터로, None이면 보내지 않는다.
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15140153/openapi.do + 외부 구현 실호출 params.
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    if search_day:
        params[PARAM_SEARCH_DAY] = search_day
    params[PARAM_FROM_TIME] = from_time
    params[PARAM_TO_TIME] = to_time
    if airport_code:
        params[PARAM_AIRPORT_CODE] = airport_code
    if flight_id:
        params[PARAM_FLIGHT_ID] = flight_id
    params[PARAM_LANG] = lang
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투: {"response": {"header": {"resultCode","resultMsg"},
#        "body": {"items": [...], "totalCount","pageNo","numOfRows"}}}.
# ⚠️ 인천공항 quirk: body.items는 **곧장 리스트**(TAGO/airkorea의 items.item 중첩과 다름).
#   1건이면 단일 객체, 0건이면 빈 리스트/빈 문자열일 수 있다. normalize_items가 흡수한다.
# 편명/시각/터미널/게이트 등은 상류가 **문자열 또는 숫자**로 섞어 줄 수 있어 전부 str | None로
# 받고(캐스팅 강제 금지) 결측은 None/"-"로 다룬다. extra="ignore"로 느슨히(언어/오퍼레이션별
# 필드차 흡수).
# 출처: 15140153 응답 항목 + 외부 구현 실응답 필드명 교차확인.


def _coerce_str(v: Any) -> str | None:
    """상류가 숫자/문자 섞어 주는 값을 표시용 문자열로 정규화한다(None은 그대로)."""
    if v is None:
        return None
    return str(v)


class Header(BaseModel):
    """응답 헤더 봉투 `{resultCode, resultMsg}`.

    resultCode != "00"이면 에러(서비스키 오류·데이터 없음 등). 출처: data.go.kr 응답 header.
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None


class PassengerFlight(BaseModel):
    """여객편 운항현황 항목(도착·출발 공통 + 방향별 필드).

    공통 필드(실응답 교차확인):
      - airline(항공사명) · flightId(편명) · airport(출발지/도착지 공항명) ·
        airportCode(출발지/도착지 공항코드) · scheduleDateTime(예정시각 YYYYMMDDHHMM) ·
        estimatedDateTime(변경/예상시각) · terminalid(터미널 코드 **P01/P02/P03**) ·
        gatenumber(탑승구) · remark(운항상태: 출발/도착/지연/결항 등) ·
        fid(공항 내부 항공편 식별자) · codeshare(단독/공동운항 구분: Master/Slave 등) ·
        masterflightid(공동운항 시 주 편명).
    도착 전용: carousel(수하물 수취대) · exitnumber(출구).
    출발 전용: chkinrange(체크인 카운터 범위).
    ⚠️ terminalid는 표시명(T1/T2)이 아니라 **코드(P01=제1터미널·P02=탑승동·P03=제2터미널)**다 —
      tools._fmt_terminal로 표시명 환산. 출처: 외부 구현(airscreen iOS·convention C#: P01/P02/P03).
    출처: https://www.data.go.kr/data/15140153/openapi.do +
      외부 구현(item.get('airline'/'flightId'/'scheduleDateTime'/'estimatedDateTime'/
      'terminalid'/'gatenumber'/'remark'/'fid'/'airportCode'/'codeshare'/'masterflightid');
      도착 carousel/exitnumber; 출발 chkinrange)으로 다중 교차확인(aivle ICN-AI-chatbot Python,
      eyjs/convention C#, airscreen iOS Swift·Android Kotlin, TaeHyun77 Java).
    TODO(provenance): `city`/`typeOfFlight`/`fstandposition` 등 일부 변형은 상세 페이지가 JS
      렌더라 인라인 스키마를 정적으로 못 봤고 단일 구현에서만 보여 모델에 두지 않는다. 다중 외부
      구현으로 확인된 위 필드만 모델에 두고, extra="ignore"로 나머지 변형을 흡수한다.
    """

    model_config = {"extra": "ignore"}

    airline: str | None = None
    flightId: str | None = None
    airport: str | None = None
    airportCode: str | None = None
    scheduleDateTime: str | None = None
    estimatedDateTime: str | None = None
    terminalid: str | None = None
    gatenumber: str | None = None
    remark: str | None = None
    fid: str | None = None
    codeshare: str | None = None  # 단독/공동운항 구분(Master/Slave 등)
    masterflightid: str | None = None  # 공동운항 시 주 편명
    # 도착 전용
    carousel: str | None = None
    exitnumber: str | None = None
    # 출발 전용
    chkinrange: str | None = None

    @field_validator(
        "flightId",
        "airportCode",
        "scheduleDateTime",
        "estimatedDateTime",
        "terminalid",
        "gatenumber",
        "carousel",
        "exitnumber",
        "chkinrange",
        "fid",
        "codeshare",
        "masterflightid",
        mode="before",
    )
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


def normalize_items(items: Any) -> list[dict]:
    """body.items를 항목 dict 리스트로 정규화한다(인천공항 + data.go.kr 공통 quirk 흡수).

    흡수하는 형태:
      - items가 None / 빈 문자열 ""(0건) → []
      - items가 곧장 리스트(인천공항 기본형) → [...]
      - items가 단일 dict(1건) → [{...}]
      - items == {"item": {...}} / {"item": [...]}(타 data.go.kr 서비스형) → 평탄화
    출처: 인천공항 실응답(`body.items`가 곧장 리스트, 1건이면 객체) +
      data.go.kr 공통 직렬화(XML <items><item> → {"items":{"item":…}}).
    """
    if items is None or items == "":
        return []
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    if isinstance(items, dict):
        # data.go.kr 공통형: {"item": …} 한 단계 더 싸인 경우.
        if "item" in items:
            item = items.get("item")
            if item is None or item == "":
                return []
            if isinstance(item, list):
                return [i for i in item if isinstance(i, dict)]
            if isinstance(item, dict):
                return [item]
            return []
        # 인천공항형: 단일 항목이 곧장 dict.
        return [items]
    return []


class Body(BaseModel):
    """응답 body 봉투(items + 페이지네이션).

    items는 raw로 받아 normalize_items로 평탄화한다(인천공항: 직접 리스트/단일 객체, 타 서비스:
    item 중첩, 0건: 빈 문자열).
    출처: 15140153 응답 body(totalCount/pageNo/numOfRows).
    """

    model_config = {"extra": "ignore"}

    items: Any = None
    totalCount: int | None = None
    pageNo: int | None = None
    numOfRows: int | None = None

    @field_validator("totalCount", "pageNo", "numOfRows", mode="before")
    @classmethod
    def _v_int(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def item_dicts(self) -> list[dict]:
        """body.items를 항목 dict 리스트로 정규화."""
        return normalize_items(self.items)


class Response(BaseModel):
    """전체 응답 봉투 `{response:{header, body}}`.

    게이트웨이 차단 시 `{response:{header:{resultCode, resultMsg}}}`만 오거나, 키 차단은
    `cmmMsgHeader/returnReasonCode`로도 올 수 있다(tools에서 보조 검사).
    출처: 15140153 응답 봉투 + data.go.kr 공통 규약.
    """

    model_config = {"extra": "ignore"}

    header: Header | None = None
    body: Body | None = None
