"""TAGO(국가대중교통정보센터) 전국 대중교통 통합 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, 응답 봉투/항목 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. 국토부 TAGO는 **단일 네임스페이스 `1613000`**에 전국 대중교통(버스·철도·
고속/시외)이 통합돼 있어 **하나의 data.go.kr 서비스키로 전부 커버**한다. 인증은 OAuth가 아니라
**쿼리 파라미터 `serviceKey`**다(헤더 아님). 응답은 기본 XML이라 **`_type=json`을 명시**한다.
페이지네이션/건수는 응답 **본문**(`response.body.totalCount/pageNo/numOfRows`)에 실린다.

⚠️ data.go.kr 서비스키 함정(airkorea/egen 동일): 키는 **Encoding/Decoding 2종**으로 발급된다.
httpx가 쿼리 파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를 넣어 이중
인코딩을 피한다.

⚠️ data.go.kr `_type=json` 봉투 quirk: items는 **`{"items": {"item": [...] }}`**로 한 단계 더
싸여 온다(XML `<items><item>…`의 JSON 사상). 결과가 1건이면 `item`이 **배열이 아니라 단일
객체**, 0건이면 `items`가 **빈 문자열 `""`**일 수 있다. 응답 모델은 이 셋을 모두 흡수한다.

출처(공식 — data.go.kr · 전부 TAGO 통합 네임스페이스 1613000):
  - 버스도착정보 ArvlInfoInqireService: https://www.data.go.kr/data/15098530/openapi.do
      · getSttnAcctoArvlPrearngeInfoList(정류소별 도착예정정보 목록조회)
      · getCtyCodeList(도시코드 목록조회)
  - 버스정류소정보 BusSttnInfoInqireService: https://www.data.go.kr/data/15098534/openapi.do
      · getSttnNoList(정류소번호 목록조회 — 정류소명 검색)
  - 버스노선정보 BusRouteInfoInqireService: https://www.data.go.kr/data/15098529/openapi.do
      · getRouteAcctoThrghSttnList(노선별 경유정류소 목록조회)
  - 고속버스정보 ExpBusInfoService: https://www.data.go.kr/data/15098522/openapi.do
      · getStrtpntAlocFndExpbusInfo(출/도착지기반 고속버스정보 조회)
  - 시외버스정보 SuburbsBusInfoService: https://www.data.go.kr/data/15098541/openapi.do
      · getStrtpntAlocFndSuberbsBusInfo(출/도착지기반 시외버스정보 조회)
  - 열차정보 TrainInfoService: https://www.data.go.kr/data/15098552/openapi.do
      · getStrtpntAlocFndTrainInfo(출/도착지기반 열차정보 조회 — depPlaceId·arrPlaceId·depPlandTime)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from arcsolve.services._datagokr import clamp_paging

# ─── base URL / 서비스 경로 상수 ────────────────────────────
# 전국 대중교통 통합 네임스페이스. 출처: 위 6개 data.go.kr 페이지 공통.
BASE_URL = "https://apis.data.go.kr/1613000"

# 서비스(엔드포인트 그룹) 경로.
# 출처: data.go.kr 페이지 + [국토교통부] TAGO OPEN API 대체 공지(NOTICE_0000000002723)의
#   대체 서비스명(`…Service` 형태 — 구 서비스는 22.09.01 호출중지, 이 6종이 현행 대체본).
SERVICE_BUS_ARRIVAL = "/ArvlInfoInqireService"
SERVICE_BUS_STATION = "/BusSttnInfoInqireService"
SERVICE_BUS_ROUTE = "/BusRouteInfoInqireService"
SERVICE_EXP_BUS = "/ExpBusInfoService"
SERVICE_SUBURBS_BUS = "/SuburbsBusInfoService"
SERVICE_TRAIN = "/TrainInfoService"
# 서비스 경로 접미사 `…Service`는 6종 모두 확인됨(독립 검증):
#   · 버스도착(ArvlInfoInqireService)·정류소(BusSttnInfoInqireService)·노선(BusRouteInfoInqireService)
#     는 data.go.kr 상세 페이지 Service URL 라벨로 직접 확인.
#   · 고속(ExpBusInfoService)·시외(SuburbsBusInfoService)·열차(TrainInfoService)는 다수 외부
#     구현의 실호출 URL로 교차확인(예: .../1613000/ExpBusInfoService/getStrtpntAlocFndExpbusInfo,
#     .../1613000/TrainInfoService/getStrtpntAlocFndTrainInfo). 전부 `…Service` 접미사 포함.

# ─── 오퍼레이션 경로 상수 ───────────────────────────────────
# 출처: 각 서비스 data.go.kr 상세 페이지의 상세기능 목록.
OP_BUS_ARRIVAL = "/getSttnAcctoArvlPrearngeInfoList"  # 정류소별 도착예정정보 목록조회
OP_CITY_CODE = "/getCtyCodeList"  # 도시코드 목록조회(버스 서비스 공통)
OP_STATION_SEARCH = "/getSttnNoList"  # 정류소번호 목록조회(정류소명 검색)
OP_ROUTE_STATIONS = "/getRouteAcctoThrghSttnList"  # 노선별 경유정류소 목록조회
OP_EXP_BUS = "/getStrtpntAlocFndExpbusInfo"  # 출/도착지기반 고속버스정보 조회
OP_SUBURBS_BUS = "/getStrtpntAlocFndSuberbsBusInfo"  # 출/도착지기반 시외버스정보 조회
OP_TRAIN = "/getStrtpntAlocFndTrainInfo"  # 출/도착지기반 열차정보 조회(역ID·출발일)


# ─── 쿼리 파라미터명(공식) ──────────────────────────────────
# 출처: 위 6개 data.go.kr 페이지(요청변수 표).
PARAM_SERVICE_KEY = "serviceKey"
PARAM_TYPE = "_type"
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_PAGE_NO = "pageNo"
PARAM_CITY_CODE = "cityCode"
PARAM_NODE_ID = "nodeId"
PARAM_NODE_NM = "nodeNm"
PARAM_ROUTE_ID = "routeId"
PARAM_DEP_TERMINAL_ID = "depTerminalId"
PARAM_ARR_TERMINAL_ID = "arrTerminalId"
PARAM_DEP_PLACE_ID = "depPlaceId"
PARAM_ARR_PLACE_ID = "arrPlaceId"
PARAM_DEP_PLAND_TIME = "depPlandTime"  # 출발일 YYYYMMDD

# `_type=json`을 명시하지 않으면 상류가 기본 XML을 줘 get_json이 파싱하지 못한다.
TYPE_JSON = "json"

# 공통 페이지네이션 기본값. 출처: 위 페이지(numOfRows 기본 10, pageNo 기본 1).
DEFAULT_NUM_OF_ROWS = 100  # 기본은 10이나 실용상 100으로 받는다(상한은 서비스별 상이).
DEFAULT_PAGE_NO = 1
# numOfRows/pageNo 안전 범위.
# TODO(provenance): numOfRows 상한이 서비스별 상이하고 상세 페이지에 인라인 명시되지 않아,
#   data.go.kr 게이트웨이 통용 상한 9999를 보수적 상한으로 둔다(위반 시 결과코드 10 방지). 하한 1.
MAX_NUM_OF_ROWS = 9999
MIN_NUM_OF_ROWS = 1

# 정상 응답 결과코드. 출처: data.go.kr 공통 OpenAPI 에러코드 규약 + 위 페이지 응답 header.
RESULT_CODE_OK = "00"


def _base(service_key: str, *, with_type: bool = True) -> dict[str, str | int]:
    """모든 TAGO 요청의 공통 베이스 파라미터(serviceKey·_type)."""
    params: dict[str, str | int] = {PARAM_SERVICE_KEY: service_key}
    if with_type:
        params[PARAM_TYPE] = TYPE_JSON
    return params


def build_city_code_params(*, service_key: str) -> dict[str, str | int]:
    """도시코드 목록(getCtyCodeList) 쿼리스트링.

    cityCode 등 추가 입력 없이 전국 도시코드 목록을 받는다.
    출처: https://www.data.go.kr/data/15098530/openapi.do (getCtyCodeList).
    """
    return _base(service_key)


def build_station_search_params(
    *,
    city_code: str,
    node_name: str,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """정류소명 검색(getSttnNoList) 쿼리스트링.

    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15098534/openapi.do (getSttnNoList — cityCode·nodeNm).
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    params[PARAM_CITY_CODE] = city_code
    params[PARAM_NODE_NM] = node_name
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


def build_bus_arrival_params(
    *,
    city_code: str,
    node_id: str,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """정류소별 도착예정정보(getSttnAcctoArvlPrearngeInfoList) 쿼리스트링.

    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15098530/openapi.do (cityCode·nodeId 필수).
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    params[PARAM_CITY_CODE] = city_code
    params[PARAM_NODE_ID] = node_id
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


def build_route_stations_params(
    *,
    city_code: str,
    route_id: str,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """노선별 경유정류소(getRouteAcctoThrghSttnList) 쿼리스트링.

    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15098529/openapi.do (cityCode·routeId 필수).
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    params[PARAM_CITY_CODE] = city_code
    params[PARAM_ROUTE_ID] = route_id
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


def build_terminal_bus_params(
    *,
    dep_terminal_id: str,
    arr_terminal_id: str,
    dep_date: str,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """고속/시외버스 운행(getStrtpntAlocFnd…) 쿼리스트링(터미널ID 기반).

    고속(ExpBusInfoService)·시외(SuburbsBusInfoService)가 동형 파라미터를 쓴다.
    depPlandTime은 출발일 `YYYYMMDD`.
    출처: https://www.data.go.kr/data/15098522/openapi.do ·
          https://www.data.go.kr/data/15098541/openapi.do
          (depTerminalId·arrTerminalId·depPlandTime).
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    params[PARAM_DEP_TERMINAL_ID] = dep_terminal_id
    params[PARAM_ARR_TERMINAL_ID] = arr_terminal_id
    params[PARAM_DEP_PLAND_TIME] = dep_date
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


def build_train_params(
    *,
    dep_station_id: str,
    arr_station_id: str,
    dep_date: str,
    service_key: str,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """도시간 열차(getCtyAcctoTrainList) 쿼리스트링(역ID 기반).

    depPlaceId/arrPlaceId는 역코드, depPlandTime은 출발일 `YYYYMMDD`.
    출처: https://www.data.go.kr/data/15098552/openapi.do
          (depPlaceId·arrPlaceId·depPlandTime).
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params = _base(service_key)
    params[PARAM_DEP_PLACE_ID] = dep_station_id
    params[PARAM_ARR_PLACE_ID] = arr_station_id
    params[PARAM_DEP_PLAND_TIME] = dep_date
    params[PARAM_NUM_OF_ROWS] = num_of_rows
    params[PARAM_PAGE_NO] = page_no
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투: {"response": {"header": {"resultCode","resultMsg"},
#        "body": {"items": {"item": [...] }, "totalCount","pageNo","numOfRows"}}}.
# data.go.kr `_type=json` quirk: items는 한 단계 더(`{"item": …}`) 싸이고, item은 1건이면
# 배열이 아닌 단일 객체, 0건이면 items가 빈 문자열 "". _ItemsBody가 셋을 흡수한다.
# 코드(citycode/nodeid/routeid 등)·요금·시각은 상류가 **문자열 또는 숫자**로 섞어 줄 수 있어
# 전부 str | None로 받고(캐스팅 강제 금지) 결측은 None/"-"로 다룬다.
# extra="ignore"로 느슨히(서비스/오퍼레이션별 필드차 흡수).
# 출처: 위 6개 data.go.kr 페이지 응답 항목.


def _coerce_str(v: Any) -> str | None:
    """상류가 숫자/문자 섞어 주는 값을 표시용 문자열로 정규화한다(None은 그대로)."""
    if v is None:
        return None
    return str(v)


class Header(BaseModel):
    """응답 헤더 봉투 `{resultCode, resultMsg}`.

    resultCode != "00"이면 에러(서비스키 오류·데이터 없음 등). 출처: 위 페이지 응답 header.
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None


class CityCode(BaseModel):
    """도시코드 항목(getCtyCodeList).

    공식 필드: citycode(도시코드) · cityname(도시명).
    출처: https://www.data.go.kr/data/15098530/openapi.do (getCtyCodeList).
    """

    model_config = {"extra": "ignore"}

    citycode: str | None = None
    cityname: str | None = None

    @field_validator("citycode", mode="before")
    @classmethod
    def _v_code(cls, v: Any) -> str | None:
        return _coerce_str(v)


class BusStop(BaseModel):
    """정류소 항목(getSttnNoList).

    공식 필드: nodeid(정류소ID) · nodenm(정류소명) · nodeno(정류소번호) ·
      gpslati/gpslong(WGS84 위경도) · citycode(도시코드).
    출처: https://www.data.go.kr/data/15098534/openapi.do (정류소 항목).
    """

    model_config = {"extra": "ignore"}

    nodeid: str | None = None
    nodenm: str | None = None
    nodeno: str | None = None
    gpslati: str | None = None
    gpslong: str | None = None
    citycode: str | None = None

    @field_validator("nodeno", "gpslati", "gpslong", "citycode", mode="before")
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class BusArrival(BaseModel):
    """정류소별 도착예정 버스 항목(getSttnAcctoArvlPrearngeInfoList).

    공식 필드: nodeid/nodenm(정류소) · routeid/routeno(노선) · routetp(노선유형) ·
      arrprevstationcnt(남은 정류장 수) · vehicletp(차량유형) · arrtime(도착예상[초]).
    출처: https://www.data.go.kr/data/15098530/openapi.do (응답 항목).
    """

    model_config = {"extra": "ignore"}

    nodeid: str | None = None
    nodenm: str | None = None
    routeid: str | None = None
    routeno: str | None = None
    routetp: str | None = None
    arrprevstationcnt: str | None = None
    vehicletp: str | None = None
    arrtime: str | None = None

    @field_validator("routeno", "arrprevstationcnt", "arrtime", mode="before")
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class RouteStation(BaseModel):
    """노선 경유정류소 항목(getRouteAcctoThrghSttnList).

    공식 필드: nodeid/nodenm(정류소) · nodeno(정류소번호) · nodeord(경유 순번) ·
      gpslati/gpslong(위경도) · updowncd(상/하행 구분) · routeid.
    출처: https://www.data.go.kr/data/15098529/openapi.do (경유정류소 항목).
    TODO(provenance): nodeord/updowncd 등 일부 필드명은 동 네임스페이스 노선 응답의 표준
      필드명이나, 상세 페이지가 첫 오퍼레이션만 렌더해 인라인 표 확인이 어려웠다. extra="ignore"로
      느슨히 받아 변형을 흡수한다.
    """

    model_config = {"extra": "ignore"}

    nodeid: str | None = None
    nodenm: str | None = None
    nodeno: str | None = None
    nodeord: str | None = None
    gpslati: str | None = None
    gpslong: str | None = None
    updowncd: str | None = None
    routeid: str | None = None

    @field_validator("nodeno", "nodeord", "gpslati", "gpslong", "updowncd", mode="before")
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class TerminalBus(BaseModel):
    """고속/시외버스 운행 항목(getStrtpntAlocFnd…).

    공식 필드: depPlandTime/arrPlandTime(출/도착 예정시각) · gradeNm(등급명) ·
      charge(요금) · depPlaceNm/arrPlaceNm(출/도착 터미널명) · routeId.
    출처: https://www.data.go.kr/data/15098522/openapi.do (고속) ·
          https://www.data.go.kr/data/15098541/openapi.do (시외).
      필드명은 다수 외부 구현으로 교차확인됨(카멜 표기: gradeNm/charge/depPlandTime/arrPlandTime/
      depPlaceNm/arrPlaceNm/routeId). 응답 depPlandTime/arrPlandTime은 YYYYMMDDHHMM(요청
      depPlandTime은 출발일 YYYYMMDD). extra="ignore"로 변형을 흡수한다.
    """

    model_config = {"extra": "ignore"}

    depPlandTime: str | None = None
    arrPlandTime: str | None = None
    gradeNm: str | None = None
    charge: str | None = None
    depPlaceNm: str | None = None
    arrPlaceNm: str | None = None
    routeId: str | None = None

    @field_validator("charge", mode="before")
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


class Train(BaseModel):
    """출/도착지기반 열차 운행 항목(getStrtpntAlocFndTrainInfo).

    공식 필드: depplandtime/arrplandtime(출/도착 예정시각) · traingradename(열차등급명, KTX 등) ·
      trainno(열차번호) · depplacename/arrplacename(출/도착역명) · adultcharge(어른 요금).
    출처: https://www.data.go.kr/data/15098552/openapi.do (열차 응답 항목).
      필드명은 다수 외부 구현으로 교차확인됨(소문자 표기: depplandtime/arrplandtime/traingradename/
      trainno/depplacename/arrplacename/adultcharge). extra="ignore"로 변형을 흡수한다.
    """

    model_config = {"extra": "ignore"}

    depplandtime: str | None = None
    arrplandtime: str | None = None
    traingradename: str | None = None
    trainno: str | None = None
    depplacename: str | None = None
    arrplacename: str | None = None
    adultcharge: str | None = None

    @field_validator("depplandtime", "arrplandtime", "trainno", "adultcharge", mode="before")
    @classmethod
    def _v(cls, v: Any) -> str | None:
        return _coerce_str(v)


def normalize_items(items: Any) -> list[dict]:
    """data.go.kr `_type=json` 봉투의 body.items를 항목 dict 리스트로 정규화한다.

    quirk 흡수:
      - items가 빈 문자열 ""(0건) → []
      - items == {"item": {...}}(1건) → [{...}]
      - items == {"item": [...]}(N건) → [...]
      - items가 곧장 리스트/단일 dict로 와도 흡수.
    출처: data.go.kr 공통 JSON 직렬화 규약(XML <items><item> → {"items":{"item":…}}).
    """
    if items is None or items == "":
        return []
    if isinstance(items, dict):
        item = items.get("item")
        if item is None or item == "":
            return []
        if isinstance(item, list):
            return [i for i in item if isinstance(i, dict)]
        if isinstance(item, dict):
            return [item]
        return []
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    return []


class Body(BaseModel):
    """응답 body 봉투(items + 페이지네이션).

    items는 raw로 받아 normalize_items로 평탄화한다(quirk: dict/"" /단일/배열).
    출처: 위 페이지 응답 body(totalCount/pageNo/numOfRows).
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
    출처: 위 6개 페이지 응답 봉투.
    """

    model_config = {"extra": "ignore"}

    header: Header | None = None
    body: Body | None = None
