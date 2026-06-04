"""전기차 충전소(한국환경공단) 정보·실시간 상태 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, **XML → pydantic 파싱**.
MCP/네트워크 무의존(순수 상수 + pydantic 모델 + 표준 라이브러리 XML 파서).

전부 GET·읽기. 인증은 **서비스키 필수**(data.go.kr 발급) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님). 응답 포맷은 **XML**이다(data.go.kr 상세 페이지의 출력 예시·활용
가이드(v1.23)가 XML 기준이며 `_type=json` 지원은 공식 확인 불가). 그래서 같은 기관(B552584)의
airkorea처럼 봉투 `response.header.resultCode`로 에러를 가르되, 본문은 egen/arxiv처럼 코어
`get_text`(raw str)로 받아 **표준 라이브러리 `xml.etree.ElementTree`**로 파싱한다
(feedparser/lxml 같은 외부 의존 금지).

⚠️ 실시간 상태 지연: getChargerStatus는 "실시간"이지만 상류가 **약 5분 주기**로 갱신한다
(요청 파라미터 `period` 기본 5분). 따라서 결과는 항상 수 분 지연된 캐시 스냅샷이다.

⚠️ data.go.kr 서비스키 함정(airkorea·egen과 동일): 키는 **Encoding/Decoding 2종**으로 발급된다.
httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를 넣어 이중
인코딩을 피한다.

⚠️ 결측/상태 문자열: 상태(`stat`)·충전기타입(`chgerType`)·위경도(`lat`/`lng`)·플래그(`*Yn`)는
전부 **문자열**로 온다. 결측은 빈 값일 수 있어 캐스팅하지 않는다(airkorea·egen과 동형).

출처(공식 — data.go.kr):
  - 한국환경공단_전기자동차 충전소 정보 OpenAPI(EvCharger) 상세
    (base URL·오퍼레이션·요청 파라미터 serviceKey/pageNo/numOfRows/period/zcode·
     getChargerStatus 응답 필드·stat 코드 의미·실시간 5분 갱신):
    https://www.data.go.kr/data/15076352/openapi.do
  - 전국전기차충전소표준데이터(필드 한글 라벨 교차참조):
    https://www.data.go.kr/data/15013115/standard.do
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from arcsolve.services._datagokr import clamp_paging
from arcsolve.xml import safe_fromstring

from pydantic import BaseModel

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base·오퍼레이션): https://www.data.go.kr/data/15076352/openapi.do
BASE_URL = "https://apis.data.go.kr/B552584/EvCharger"
# 충전소 정보 조회(충전소·충전기 위치/타입/운영기관/이용가능시간)
PATH_CHARGER_INFO = "/getChargerInfo"
# 충전기 상태 실시간 제공(충전중/대기/통신이상 + 상태갱신일시; 약 5분 갱신)
PATH_CHARGER_STATUS = "/getChargerStatus"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 공통 파라미터명. 출처: https://www.data.go.kr/data/15076352/openapi.do
PARAM_SERVICE_KEY = "serviceKey"
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_PAGE_NO = "pageNo"
PARAM_PERIOD = "period"  # getChargerStatus 전용(상태갱신 조회범위, 분 단위)
PARAM_ZCODE = "zcode"  # 시도 코드(행정구역코드 앞 2자리) — 선택
PARAM_ZSCODE = "zscode"  # 시군구 코드 — 선택

# 공통 페이지네이션 기본값/제약.
# 출처: https://www.data.go.kr/data/15076352/openapi.do (numOfRows 최소 10·최대 9999).
DEFAULT_NUM_OF_ROWS = 100
DEFAULT_PAGE_NO = 1
MIN_NUM_OF_ROWS = 10
MAX_NUM_OF_ROWS = 9999

# getChargerStatus `period`(상태갱신 조회범위, 분): 기본 5·최소 1·최대 10.
# 출처: https://www.data.go.kr/data/15076352/openapi.do (요청 파라미터 period).
# ⚠️ 상태는 약 5분 주기로 갱신 → 결과는 수 분 지연된 캐시 스냅샷이다.
DEFAULT_PERIOD = 5
MIN_PERIOD = 1
MAX_PERIOD = 10

# 정상 응답 결과코드. 출처: data.go.kr(공통 OpenAPI 에러코드 규약 + 위 페이지 응답 header).
RESULT_CODE_OK = "00"

# 충전기 상태 코드(stat) → 사람이 읽을 한글 의미.
# 출처: https://www.data.go.kr/data/15076352/openapi.do (getChargerStatus 응답 stat 설명).
STAT_LABELS = {
    "1": "통신이상",
    "2": "충전대기",
    "3": "충전중",
    "4": "운영중지",
    "5": "점검중",
    "9": "상태미확인",
}

# 충전기 타입 코드(chgerType) → 한글 의미.
# 출처: 한국환경공단 EvCharger 활용가이드(v1.23) 코드표 + 전국전기차충전소표준데이터
#   https://www.data.go.kr/data/15013115/standard.do
#   + 다수 외부 구현 교차확인(09=NACS·10=DC콤보+NACS 등 최신 코드):
#   heeaayoon/KDT_React01(src/19/chgertype.json) · EJGo-712/EVCar(ChargerResponseDto.java) ·
#   seung-2001/evdesign(StationInfo.jsx) · EVeryCharge(ChargingStationStateTable.js).
# TODO(provenance): chgerType 코드표는 data.go.kr 상세 페이지에 인라인 렌더되지 않고 다운로드
#   활용가이드(.docx)에만 표로 있어, 위 외부 구현으로 교차확인했다. 01~08은 다수 구현이 만장일치,
#   09(NACS·테슬라)·10(DC콤보+NACS)은 복수 구현 일치. 더 최신(11=DC콤보2 버스전용 등)은 구현마다
#   편차가 있어 싣지 않고, **미상 코드는 표시 시 원본 코드를 그대로 보존한다**(매핑 없으면 코드 노출).
CHGER_TYPE_LABELS = {
    "01": "DC차데모",
    "02": "AC완속",
    "03": "DC차데모+AC3상",
    "04": "DC콤보",
    "05": "DC차데모+DC콤보",
    "06": "DC차데모+AC3상+DC콤보",
    "07": "AC3상",
    "08": "DC콤보(완속)",
    "09": "NACS",
    "10": "DC콤보+NACS",
}


def _clamp(value: int, lo: int, hi: int) -> int:
    """value를 [lo, hi]로 클램프한다(상류 제약 위반 호출을 사전에 방지).

    period(분 단위, 비-페이지 파라미터) 전용. numOfRows/pageNo는 공유 clamp_paging을 쓴다.
    """
    return max(lo, min(hi, value))


def _base_params(
    *,
    service_key: str,
    zcode: str | None,
    zscode: str | None,
    num_of_rows: int,
    page_no: int,
) -> dict[str, str | int]:
    """두 오퍼레이션 공통 쿼리스트링(serviceKey·지역코드·페이지네이션).

    serviceKey는 **Decoding 키 원문**을 넣는다(httpx가 자동 인코딩 → 이중 인코딩 방지).
    zcode(시도)·zscode(시군구)는 빈 값이면 생략한다(미지정 → 전국/시도 전체).
    numOfRows/pageNo는 공유 헬퍼로 상류 제약 [10, 9999]·pageNo≥1로 클램프한다.
    출처: https://www.data.go.kr/data/15076352/openapi.do
    """
    num_of_rows, page_no = clamp_paging(
        num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS, min_rows=MIN_NUM_OF_ROWS
    )
    params: dict[str, str | int] = {
        PARAM_SERVICE_KEY: service_key,
        PARAM_PAGE_NO: page_no,
        PARAM_NUM_OF_ROWS: num_of_rows,
    }
    if zcode:
        params[PARAM_ZCODE] = zcode
    if zscode:
        params[PARAM_ZSCODE] = zscode
    return params


def build_charger_info_params(
    *,
    service_key: str,
    zcode: str | None = None,
    zscode: str | None = None,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """충전소 정보 조회(getChargerInfo) 쿼리스트링을 만든다.

    출처: https://www.data.go.kr/data/15076352/openapi.do
    """
    return _base_params(
        service_key=service_key, zcode=zcode, zscode=zscode,
        num_of_rows=num_of_rows, page_no=page_no,
    )


def build_charger_status_params(
    *,
    service_key: str,
    zcode: str | None = None,
    zscode: str | None = None,
    period: int = DEFAULT_PERIOD,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """충전기 상태 실시간 조회(getChargerStatus) 쿼리스트링을 만든다.

    period(상태갱신 조회범위, 분)는 상류 제약 [1, 10]으로 클램프한다(기본 5).
    ⚠️ 상태는 약 5분 주기 갱신 → 결과는 수 분 지연된 캐시 스냅샷이다.
    출처: https://www.data.go.kr/data/15076352/openapi.do
    """
    params = _base_params(
        service_key=service_key, zcode=zcode, zscode=zscode,
        num_of_rows=num_of_rows, page_no=page_no,
    )
    params[PARAM_PERIOD] = _clamp(period, MIN_PERIOD, MAX_PERIOD)
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투(data.go.kr 공통): <response><header><resultCode/><resultMsg/></header>
#   <body><items><item>...</item></items><numOfRows/><pageNo/><totalCount/></body></response>.
# 모든 속성/상태/좌표 필드는 **문자열**로 받는다(상태='2'·타입='04'·위경도='37.5'·플래그='Y'/'N',
# 결측=빈 값). extra="ignore"로 느슨히(오퍼레이션/가이드 버전 필드차 흡수).
# 출처: https://www.data.go.kr/data/15076352/openapi.do


class Header(BaseModel):
    """응답 헤더 봉투 `{resultCode, resultMsg}`.

    resultCode != "00"이면 에러(서비스키 오류 등). data.go.kr는 한글/영문 메시지를 섞어 준다.
    출처: 위 페이지 응답 header(resultCode/resultMsg).
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None


class Charger(BaseModel):
    """충전소·충전기 정보 항목(getChargerInfo, 부분).

    공식 필드(출처: https://www.data.go.kr/data/15076352/openapi.do getChargerStatus 응답 +
    EvCharger 활용가이드(v1.23) + 전국전기차충전소표준데이터 한글 라벨):
      statId(충전소ID) · statNm(충전소명) · chgerId(충전기ID) · chgerType(충전기타입 코드) ·
      addr(주소) · location(상세위치) · lat(위도) · lng(경도) · useTime(이용가능시간) ·
      busiId(기관ID) · bnmm(충전소설치업체명) · busiNm(운영기관명) · busiCall(운영기관 연락처) ·
      zcode(지역코드 시도) · zscode(지역코드 시군구) · kind(충전소구분 코드) ·
      kindDetail(충전소구분 상세 코드) · parkingFree(주차료 무료여부 Y/N) · note(안내) ·
      limitYn(이용자제한 Y/N) · limitDetail(이용제한 사유) · delYn(삭제 여부 Y/N) ·
      delDetail(삭제 사유) · trafficYn(경로안내 가능여부) · output(충전용량 kW) ·
      method(충전방식) · stat(충전기상태 코드) · statUpdDt(상태갱신일시).
    값은 전부 문자열(결측은 빈 값). 캐스팅하지 않는다.
    # TODO(provenance): getChargerInfo 응답 필드 전체 표는 data.go.kr 상세 페이지에 인라인
    #   렌더되지 않고 다운로드 활용가이드(.docx v1.23)에만 있다(getChargerStatus만 인라인 확인).
    #   인라인 확인된 공통 식별/상태 필드(statId·chgerId·stat·statUpdDt·busiId·zcode 등)에 더해
    #   표준데이터(15013115)에서 교차확인된 정보 필드를 모델링하고, extra="ignore"로 느슨히 받아
    #   가이드 버전차/미확인 필드를 흡수한다.
    출처: https://www.data.go.kr/data/15076352/openapi.do
    """

    model_config = {"extra": "ignore"}

    statId: str | None = None
    statNm: str | None = None
    chgerId: str | None = None
    chgerType: str | None = None
    addr: str | None = None
    location: str | None = None
    lat: str | None = None
    lng: str | None = None
    useTime: str | None = None
    busiId: str | None = None
    bnmm: str | None = None
    busiNm: str | None = None
    busiCall: str | None = None
    zcode: str | None = None
    zscode: str | None = None
    kind: str | None = None
    kindDetail: str | None = None
    parkingFree: str | None = None
    note: str | None = None
    limitYn: str | None = None
    limitDetail: str | None = None
    delYn: str | None = None
    delDetail: str | None = None
    trafficYn: str | None = None
    output: str | None = None
    method: str | None = None
    stat: str | None = None
    statUpdDt: str | None = None


class ChargerStatus(BaseModel):
    """충전기 상태 실시간 항목(getChargerStatus, 부분).

    공식 필드(출처: https://www.data.go.kr/data/15076352/openapi.do getChargerStatus 응답):
      busiId(기관ID) · statId(충전소ID) · chgerId(충전기ID) · stat(충전기상태 코드) ·
      statUpdDt(충전기 상태 변경 일시, 예 '20190829121020').
    추가(활용가이드 v1.23 — getChargerStatus 확장 필드): lastTsdt(마지막 충전 시작일시) ·
      lastTedt(마지막 충전 종료일시) · nowTsdt(충전중 시작일시) · output(충전용량) ·
      method(충전방식) · delYn(삭제 여부) · delDetail(삭제 사유).
    값은 전부 문자열(결측은 빈 값). 캐스팅하지 않는다.
    ⚠️ 약 5분 주기 갱신 → statUpdDt는 항상 수 분 지연된 시각이다.
    # TODO(provenance): 인라인 확인 필드는 busiId·statId·chgerId·stat·statUpdDt이며, 나머지
    #   확장 필드(lastTsdt 등)는 활용가이드(.docx v1.23) 기준이라 extra="ignore"로 느슨히 받는다.
    출처: https://www.data.go.kr/data/15076352/openapi.do
    """

    model_config = {"extra": "ignore"}

    busiId: str | None = None
    statId: str | None = None
    chgerId: str | None = None
    stat: str | None = None
    statUpdDt: str | None = None
    lastTsdt: str | None = None
    lastTedt: str | None = None
    nowTsdt: str | None = None
    output: str | None = None
    method: str | None = None
    delYn: str | None = None
    delDetail: str | None = None


# ─── XML → 모델 파싱 ────────────────────────────────────────
# data.go.kr XML은 네임스페이스가 없는 평면 트리다(<response><header/><body><items><item/>…).
# 출처: https://www.data.go.kr/data/15076352/openapi.do (응답 출력 예시).


def _text(el: ET.Element | None) -> str | None:
    """요소 텍스트를 trim해 돌려준다(없으면 None). 빈 문자열도 None."""
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def parse_header(root: ET.Element) -> Header:
    """봉투 <header>에서 resultCode/resultMsg를 뽑는다(없으면 빈 Header).

    data.go.kr 게이트웨이 키 오류는 <header> 없이 <cmmMsgHeader><returnReasonCode/>로 올 수
    있어, header가 비면 cmmMsgHeader도 훑어 resultCode/resultMsg를 채운다(egen과 동형).
    출처: https://www.data.go.kr/data/15076352/openapi.do + data.go.kr 공통 에러 봉투.
    """
    header = root.find("header")
    if header is not None:
        return Header(
            resultCode=_text(header.find("resultCode")),
            resultMsg=_text(header.find("resultMsg")),
        )
    # 게이트웨이 공통 에러 봉투(OpenAPI_ServiceResponse/cmmMsgHeader)
    cmm = root.find(".//cmmMsgHeader")
    if cmm is not None:
        return Header(
            resultCode=_text(cmm.find("returnReasonCode")),
            resultMsg=_text(cmm.find("returnAuthMsg")) or _text(cmm.find("errMsg")),
        )
    return Header()


def _items(root: ET.Element) -> list[ET.Element]:
    """<body><items><item>* 목록을 돌려준다(없으면 빈 리스트)."""
    return root.findall(".//body/items/item")


Page = tuple[int | None, int | None, int | None]  # (totalCount, pageNo, numOfRows)


def parse_page(root: ET.Element) -> Page:
    """<body>의 (totalCount, pageNo, numOfRows)를 int로 파싱한다(없으면 None)."""

    def _int(tag: str) -> int | None:
        t = _text(root.find(f".//body/{tag}"))
        if t is None:
            return None
        try:
            return int(t)
        except ValueError:
            return None

    return _int("totalCount"), _int("pageNo"), _int("numOfRows")


def _item_fields(item: ET.Element) -> dict[str, str]:
    """<item>의 자식 요소를 {tag: 텍스트} dict로 모은다(빈 텍스트는 제외)."""
    return {c.tag: c.text.strip() for c in item if c.text and c.text.strip()}


def parse_charger_info(xml_text: str) -> tuple[Header, list[Charger], Page]:
    """충전소 정보 XML을 (Header, items, page)로 파싱한다.

    XML이 깨졌으면 ET.ParseError가 올라간다(호출부가 매핑).
    출처: https://www.data.go.kr/data/15076352/openapi.do
    """
    root = safe_fromstring(xml_text)
    header = parse_header(root)
    items = [Charger(**_item_fields(item)) for item in _items(root)]
    return header, items, parse_page(root)


def parse_charger_status(xml_text: str) -> tuple[Header, list[ChargerStatus], Page]:
    """충전기 실시간 상태 XML을 (Header, items, page)로 파싱한다.

    출처: https://www.data.go.kr/data/15076352/openapi.do
    """
    root = safe_fromstring(xml_text)
    header = parse_header(root)
    items = [ChargerStatus(**_item_fields(item)) for item in _items(root)]
    return header, items, parse_page(root)
