"""한국교통안전공단(KOTSA) 전국 주차정보 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, 응답 봉투/항목 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. KOTSA '주차정보 제공 API'는 **단일 base `B553881/Parking`** 아래 3개
오퍼레이션(시설정보·운영정보·실시간정보)으로 나뉘며, **하나의 data.go.kr 서비스키로 전부
커버**한다. 인증은 OAuth가 아니라 **쿼리 파라미터 `serviceKey`**다(헤더 아님). 응답은 기본
XML이라 **`format=2`(JSON)를 명시**한다(`format` 1=XML, 2=JSON — `_type`/`returnType`이 아님).
모든 오퍼레이션은 **주차장관리번호 `prk_center_id`를 PK**로 공유한다(데이터 형식은 ITS Korea
실시간 주차정보 수집·연계 규격을 준용).

⚠️ 실시간 잔여면 커버리지 한계(공식): data.go.kr 안내에 "운영정보·실시간 주차정보는 시설정보에
비해 정보의 수가 적습니다"라고 명시됨. **실시간 잔여면은 시스템에 연동된 일부 주차장만** 제공되고,
표준/대다수 주차장은 정적 시설정보만 있다. 과장 금지 — 도구 설명·README에 이 한계를 명시한다.

⚠️ data.go.kr 서비스키 함정(airkorea/tago 동일): 키는 **Encoding/Decoding 2종**으로 발급된다.
httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를 넣어 이중
인코딩을 피한다.

⚠️ 봉투 quirk(B553881 고유 — tago/airkorea와 다름): JSON 응답은 표준 `response.body.items.item`
래핑이 **아니라**, 최상위에 `{resultCode, resultMsg, numOfRows, pageNo, totalCount, <오퍼레이션명>:
[항목...]}` 꼴로 온다. 즉 **항목 배열이 오퍼레이션명 키(PrkSttusInfo/PrkOprInfo/PrkRealtimeInfo)
바로 아래**에 실린다. 결과가 1건이면 배열이 아닌 **단일 객체**, 0건이면 키가 없거나 빈 값일 수 있다.
`normalize_items`가 이를 흡수한다.

출처(공식 — data.go.kr · 한국교통안전공단 주차정보 제공 API):
  - 데이터셋/오픈API 상세: https://www.data.go.kr/data/15099883/openapi.do
    · 시설정보 getPrkSttusInfo 요청주소 `…/Parking/PrkSttusInfo`(serviceKey·pageNo·numOfRows·
      format), 응답 필드 prk_center_id(PK)·prk_plce_nm·prk_plce_adres·prk_plce_entrc_la/lo·
      prk_cmprt_co는 상세 페이지의 시설정보 오퍼레이션 표에서 직접 확인.
    · base `http://apis.data.go.kr/B553881/Parking`, format(1=XML/2=JSON), PK=주차장관리번호도
      상세 페이지에서 확인.
  - 운영정보(PrkOprInfo)·실시간정보(PrkRealtimeInfo) 오퍼레이션 경로 및 응답 필드는 상세
    페이지 내려받기 기술문서(주차정보시스템 기술문서)에 정의되며, **다수 외부 구현으로 교차확인**
    (오퍼레이션명 PrkSttusInfo/PrkOprInfo/PrkRealtimeInfo, 운영필드 opertn_start_time/
    opertn_end_time/parking_chrge_bs_time/parking_chrge_bs_chrg/parking_chrge_adit_unit_time/
    parking_chrge_adit_unit_chrge, 실시간필드 pkfc_ParkingLots_total/
    pkfc_Available_ParkingLots_total). 미확정 필드는 TODO(provenance)로 표시하고 extra="ignore"로
    흡수한다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from arcsolve.services._datagokr import clamp_paging

# ─── base URL / 오퍼레이션 경로 상수 ────────────────────────
# 출처: https://www.data.go.kr/data/15099883/openapi.do (요청주소 `…/Parking/PrkSttusInfo`).
BASE_URL = "https://apis.data.go.kr/B553881/Parking"

# 오퍼레이션(엔드포인트) 경로 + JSON 항목 배열이 실리는 키(=오퍼레이션명).
# 시설정보: 상세 페이지에서 직접 확인. 운영/실시간: 다수 외부 구현으로 교차확인.
OP_FACILITY = "PrkSttusInfo"  # 주차장 시설정보(이름·주소·위경도·총주차면)
OP_OPERATION = "PrkOprInfo"  # 주차장 운영정보(운영시간·요금)
OP_REALTIME = "PrkRealtimeInfo"  # 주차장 실시간 정보(현재 주차가능면) ⭐ 연동 주차장 한정

# ─── 쿼리 파라미터명(공식) ──────────────────────────────────
# 출처: https://www.data.go.kr/data/15099883/openapi.do (요청변수 표 — 4개 전부 필수).
PARAM_SERVICE_KEY = "serviceKey"
PARAM_PAGE_NO = "pageNo"
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_FORMAT = "format"

# format=2(JSON)를 명시하지 않으면 상류가 기본 XML을 줘 get_json이 파싱하지 못한다.
# 출처: 위 페이지 요청변수("XML : 1, JSON : 2"). _type/returnType이 아니라 format이다.
FORMAT_JSON = "2"
FORMAT_XML = "1"

# 공통 페이지네이션 기본값. 출처: 위 페이지(numOfRows 샘플 10, pageNo 샘플 1).
DEFAULT_NUM_OF_ROWS = 100  # 샘플은 10이나 실용상 100으로 받는다.
DEFAULT_PAGE_NO = 1
# numOfRows/pageNo 안전 범위.
# TODO(provenance): 상세 페이지에 numOfRows 상한이 인라인 명시되지 않아, data.go.kr 게이트웨이
#   통용 상한 9999를 보수적 상한으로 둔다(위반 시 결과코드 10 방지 — 과도값 클램프). 하한 1.
MAX_NUM_OF_ROWS = 9999
MIN_NUM_OF_ROWS = 1

# 정상 응답 결과코드. 출처: 위 페이지 응답(resultCode 샘플 "00", resultMsg "SUCCESS") +
# data.go.kr 공통 OpenAPI 에러코드 규약.
RESULT_CODE_OK = "00"


def build_params(
    *,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """3개 오퍼레이션 공통 쿼리스트링(serviceKey·format=2·페이지네이션).

    세 오퍼레이션(PrkSttusInfo/PrkOprInfo/PrkRealtimeInfo)은 **동일한 4개 필수
    파라미터**만 받는다(주차장관리번호 등 추가 필터 입력 없음 — 전국 목록을 페이지로 받는다).
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15099883/openapi.do (요청변수 serviceKey·pageNo·
    numOfRows·format 4종, 전부 필수).
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    return {
        PARAM_SERVICE_KEY: service_key,
        PARAM_NUM_OF_ROWS: num_of_rows,
        PARAM_PAGE_NO: page_no,
        PARAM_FORMAT: FORMAT_JSON,
    }


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투(B553881 고유): 최상위 dict에 페이지네이션/결과코드 + **오퍼레이션명 키 아래 항목 배열**.
#   {"resultCode":"00","resultMsg":"SUCCESS","numOfRows":10,"pageNo":1,"totalCount":100,
#    "PrkSttusInfo":[{...}, ...]}
# quirk: 1건이면 오퍼레이션명 값이 배열이 아닌 단일 객체, 0건이면 키 없음/빈 값.
# 코드·요금·시각·면수는 상류가 **문자열 또는 숫자**로 섞어 줄 수 있어 전부 str | None로 받고
# (캐스팅 강제 금지) 결측은 None로 둔다. extra="ignore"로 느슨히(오퍼레이션별 필드차 흡수).
# 출처: 위 페이지 응답 항목 + 다수 외부 구현 교차확인.


def _coerce_str(v: Any) -> str | None:
    """상류가 숫자/문자 섞어 주는 값을 표시용 문자열로 정규화한다(None은 그대로)."""
    if v is None:
        return None
    return str(v)


def normalize_items(raw: Any, op_key: str) -> list[dict]:
    """B553881 응답 본문에서 오퍼레이션명 키 아래 항목 dict 리스트를 정규화한다.

    quirk 흡수:
      - 본문에 op_key가 없음(0건) → []
      - 본문[op_key] == {...}(1건, 단일 객체) → [{...}]
      - 본문[op_key] == [...](N건) → [...]
      - 본문[op_key] == ""/None(빈 값) → []
      - 일부 게이트웨이가 표준 `response.body.items.item`으로 줄 가능성도 보조 흡수.
    출처: 다수 외부 구현이 `data[<오퍼레이션명>]`로 항목 배열을 꺼냄(교차확인).
    """
    if not isinstance(raw, dict):
        return []
    items = raw.get(op_key)
    # 보조: 표준 data.go.kr 래핑(response.body.items.item)으로 올 경우.
    if items is None:
        body = raw.get("body") if isinstance(raw.get("body"), dict) else None
        if body is None and isinstance(raw.get("response"), dict):
            body = raw["response"].get("body")
        if isinstance(body, dict):
            inner = body.get("items")
            if isinstance(inner, dict):
                items = inner.get("item")
            elif inner is not None:
                items = inner
    if items is None or items == "":
        return []
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    if isinstance(items, dict):
        return [items]
    return []


class Facility(BaseModel):
    """주차장 시설정보 항목(PrkSttusInfo).

    공식 필드(상세 페이지 시설정보 표): prk_center_id(주차장관리ID·PK) · prk_plce_nm(주차장명) ·
      prk_plce_adres(도로명주소, 공백 시 지번주소) · prk_plce_entrc_la/prk_plce_entrc_lo(위/경도) ·
      prk_cmprt_co(총 주차구획 수).
    출처: https://www.data.go.kr/data/15099883/openapi.do (시설정보 응답 항목).
    TODO(provenance): prk_plce_adres_sido/prk_plce_adres_sigungu(시도·시군구 분리 주소) 및
      노상/노외/부설 구분 필드는 일부 외부 구현에서만 관측됨(상세 페이지 표 미렌더). 채택하되
      extra="ignore"로 흡수하고, 구분 필드는 추정하지 않는다.
    """

    model_config = {"extra": "ignore"}

    prk_center_id: str | None = None
    prk_plce_nm: str | None = None
    prk_plce_adres: str | None = None
    prk_plce_adres_sido: str | None = None
    prk_plce_adres_sigungu: str | None = None
    prk_plce_entrc_la: str | None = None
    prk_plce_entrc_lo: str | None = None
    prk_cmprt_co: str | None = None

    @field_validator(
        "prk_center_id",
        "prk_plce_entrc_la",
        "prk_plce_entrc_lo",
        "prk_cmprt_co",
        mode="before",
    )
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class Operation(BaseModel):
    """주차장 운영정보 항목(PrkOprInfo).

    공식 필드(기술문서 + 외부 구현 교차확인): prk_center_id(PK) · opertn_start_time/
      opertn_end_time(운영 시작/종료 시각, HHMMSS) · opertn_bs_free_time(기본 무료회차 시간[분]) ·
      parking_chrge_bs_time(기본 시간[분]) · parking_chrge_bs_chrg(기본 요금[원]) ·
      parking_chrge_adit_unit_time(추가 단위시간[분]) · parking_chrge_adit_unit_chrge(추가
      단위시간당 요금[원]).
    출처: https://www.data.go.kr/data/15099883/openapi.do (운영정보 오퍼레이션 — 경로/필드는
      내려받기 기술문서에 정의, 다수 외부 구현으로 교차확인).
    TODO(provenance): 요일별 운영시간(월~일·휴일)은 기술문서상 별도 행으로 제공될 수 있으나
      필드 표기가 구현별로 갈려(Mo_open_time 등) 단일 대표 필드(opertn_start/end_time)만 모델링.
      extra="ignore"로 추가 필드를 흡수한다.
    """

    model_config = {"extra": "ignore"}

    prk_center_id: str | None = None
    opertn_start_time: str | None = None
    opertn_end_time: str | None = None
    opertn_bs_free_time: str | None = None
    parking_chrge_bs_time: str | None = None
    parking_chrge_bs_chrg: str | None = None
    parking_chrge_adit_unit_time: str | None = None
    parking_chrge_adit_unit_chrge: str | None = None

    @field_validator(
        "prk_center_id",
        "opertn_start_time",
        "opertn_end_time",
        "opertn_bs_free_time",
        "parking_chrge_bs_time",
        "parking_chrge_bs_chrg",
        "parking_chrge_adit_unit_time",
        "parking_chrge_adit_unit_chrge",
        mode="before",
    )
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class Realtime(BaseModel):
    """주차장 실시간 정보 항목(PrkRealtimeInfo). ⭐ 연동 주차장 한정.

    공식 필드(기술문서 + 외부 구현 교차확인): prk_center_id(PK) ·
      pkfc_ParkingLots_total(주차가능 총 구획 수) · pkfc_Available_ParkingLots_total(현재 주차가능
      구획 수 — 잔여면). ⚠️ 실시간 잔여면은 **연동된 일부 주차장만** 제공된다(공식 안내: 실시간
      정보는 시설정보보다 데이터 수가 적음).
    출처: https://www.data.go.kr/data/15099883/openapi.do (실시간정보 오퍼레이션 — 경로/필드는
      내려받기 기술문서에 정의, 필드명은 다수 외부 구현의 실제 JSON 파싱으로 교차확인:
      rt.pkfc_Available_ParkingLots_total).
    """

    model_config = {"extra": "ignore"}

    prk_center_id: str | None = None
    pkfc_ParkingLots_total: str | None = None
    pkfc_Available_ParkingLots_total: str | None = None

    @field_validator(
        "prk_center_id",
        "pkfc_ParkingLots_total",
        "pkfc_Available_ParkingLots_total",
        mode="before",
    )
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class Envelope(BaseModel):
    """B553881 응답 봉투(최상위 결과코드·페이지네이션 + 오퍼레이션명 키 아래 항목).

    표준 data.go.kr 봉투(`response.header.resultCode`)와 달리 결과코드가 **최상위**에 있을 수
    있다. resultCode가 없으면(게이트웨이 차단 등) tools에서 cmmMsgHeader를 보조 검사한다.
    항목 배열은 normalize_items(raw, op_key)로 평탄화한다(quirk: 단일/배열/누락).
    출처: 위 페이지 응답(resultCode/resultMsg/totalCount/pageNo/numOfRows) + 외부 구현 교차확인.
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None
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
