"""서울 실시간 교통(지하철 도착 + 따릉이) 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 경로 빌더, 응답 봉투/항목 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. 인증은 **인증키 필수**(서울 열린데이터광장 발급)이며 OAuth가 아니다.
서울 열린데이터광장은 인증키를 **URL path의 첫 세그먼트**로 받는다(쿼리/헤더 아님):
  `http://.../{KEY}/{TYPE}/{service}/{START}/{END}/...`. `{TYPE}`에 `json`을 박아 `get_json`을 쓴다.

⚠️ 인증키 2종 분리(핵심):
  - **지하철 실시간 도착**은 별도 발급되는 **'실시간 지하철 인증키'**가 필요하다(전용 호스트
    `swopenAPI.seoul.go.kr`). env `SEOUL_SUBWAY_API_KEY`.
  - **따릉이** 등 일반 데이터셋은 표준 **'일반 인증키'**를 쓴다(호스트
    `openapi.seoul.go.kr:8088`). env `SEOUL_OPENDATA_API_KEY`.

출처(공식 — 서울 열린데이터광장 / 공공데이터포털):
  - 지하철 실시간 도착: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
    (공공데이터포털 미러: https://www.data.go.kr/data/15058052/openapi.do)
    호스트·경로 `http://swopenAPI.seoul.go.kr/api/subway/{KEY}/{TYPE}/realtimeStationArrival/{START}/{END}/{역명}`
    봉투 `{errorMessage:{status,code,message,...}, realtimeArrivalList:[...]}` — 라이브 확인.
  - 따릉이 실시간 대여정보: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
    호스트·경로 `http://openapi.seoul.go.kr:8088/{KEY}/{TYPE}/bikeList/{START}/{END}/`
    봉투 `{rentBikeStatus:{list_total_count, RESULT:{CODE,MESSAGE}, row:[...]}}` — 1회 최대 1000건.
  - 공통 결과코드(RESULT.CODE): 서울/자치구 열린데이터광장 OpenAPI 공통 메세지표
    (INFO-000 정상, INFO-100 인증키오류, INFO-200 데이터없음, ERROR-3xx 요청오류, ERROR-5xx 서버).
"""

from __future__ import annotations

from pydantic import BaseModel

# ─── 호스트 / 엔드포인트 상수 ───────────────────────────────
# 지하철 실시간 도착 — 전용 호스트(실시간 지하철 인증키).
# 출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do (라이브 확인)
SUBWAY_BASE_URL = "http://swopenAPI.seoul.go.kr/api/subway"
SUBWAY_SERVICE = "realtimeStationArrival"

# 따릉이 실시간 대여정보 — 일반 호스트(일반 인증키).
# 출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
OPENDATA_BASE_URL = "http://openapi.seoul.go.kr:8088"
BIKE_SERVICE = "bikeList"

# 응답 포맷: URL path의 {TYPE} 세그먼트. json을 박아 get_json으로 받는다(xml 회피).
TYPE_JSON = "json"

# ─── 페이지네이션 제약(공식) ───────────────────────────────
# 서울 OpenAPI는 요청 시작/종료 위치를 path 세그먼트로 받는다(START/END).
# 따릉이: 1회 최대 1000건(END - START + 1 ≤ 1000). 초과 시 ERROR-336.
# 출처: 위 따릉이 페이지 + 공통 코드(ERROR-336 "데이터요청은 한번에 최대 1000건을 넘을 수 없습니다").
BIKE_MAX_ROWS = 1000
BIKE_DEFAULT_START = 1
BIKE_DEFAULT_END = 1000

# 지하철 실시간 도착의 START/END는 페이지 위치이지만, 한 역의 도착 목록은 보통 소수다.
# 0/{N} 형태로 충분(공식 예시 `.../0/5/강남`). 우리는 넉넉히 0~20을 기본으로 둔다.
# 출처: https://www.data.go.kr/data/15058052/openapi.do (예시 `.../0/5/강남`)
SUBWAY_DEFAULT_START = 0
SUBWAY_DEFAULT_END = 20

# ─── 공통 결과코드(RESULT.CODE) — 따릉이 등 일반 봉투 ────────
# 출처(공통 메세지표): 서울/자치구 열린데이터광장 OpenAPI 공통 결과코드.
#   예: https://data.gangnam.go.kr/openinf/openapiview.jsp?infId=OA-18724
RESULT_CODE_OK = "INFO-000"


def build_subway_url(
    *,
    station_name: str,
    api_key: str,
    start: int = SUBWAY_DEFAULT_START,
    end: int = SUBWAY_DEFAULT_END,
    response_type: str = TYPE_JSON,
) -> str:
    """지하철 실시간 도착 요청 URL을 만든다.

    `{base}/{KEY}/{TYPE}/realtimeStationArrival/{START}/{END}/{역명}`.
    인증키·역명은 path 세그먼트다(쿼리 아님). 역명은 호출 측에서 그대로 넣는다
    (httpx가 path가 아닌 곳만 인코딩하므로, 한글 역명은 URL에 직접 들어간다 —
    httpx는 URL 문자열의 비ASCII path를 자동 퍼센트 인코딩한다).
    출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
    """
    return (
        f"{SUBWAY_BASE_URL}/{api_key}/{response_type}/{SUBWAY_SERVICE}"
        f"/{start}/{end}/{station_name}"
    )


def build_bike_url(
    *,
    api_key: str,
    start: int = BIKE_DEFAULT_START,
    end: int = BIKE_DEFAULT_END,
    response_type: str = TYPE_JSON,
) -> str:
    """따릉이 실시간 대여정보 요청 URL을 만든다.

    `{base}/{KEY}/{TYPE}/bikeList/{START}/{END}/`. 끝의 슬래시까지 포함한다(공식 예시 형식).
    1회 최대 1000건(END - START + 1 ≤ 1000) — 초과 시 상류가 ERROR-336을 준다.
    출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
    """
    return f"{OPENDATA_BASE_URL}/{api_key}/{response_type}/{BIKE_SERVICE}/{start}/{end}/"


# ─── 지하철 응답 모델 ──────────────────────────────────────
# 봉투(정상): {"errorMessage":{"status":200,"code":"INFO-000","message":"정상 처리되었습니다.",
#   "total":N, ...}, "realtimeArrivalList":[{...}]}.
# 에러(역명 오타·인증키 오류 등): {"errorMessage":{"status":4xx/5xx,"code":"INFO-xxx/ERROR-xxx",
#   "message":...}, "realtimeArrivalList":[]} 또는 realtimeArrivalList 키 자체가 없을 수 있다.
# 모든 항목 값은 **문자열**로 온다(시각·초 포함). extra="ignore"로 느슨히 받는다.
# 출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do (라이브 확인)


class SubwayErrorMessage(BaseModel):
    """지하철 봉투의 `errorMessage` 객체(정상이어도 항상 존재 — code=INFO-000).

    공식 필드: status(HTTP 상태 int) · code(INFO-000 정상 등) · message(설명) ·
      total(조회 건수) · link · developerMessage.
    출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    status: int | None = None
    code: str | None = None
    message: str | None = None
    total: int | None = None


class SubwayArrival(BaseModel):
    """지하철 실시간 도착 항목(부분).

    공식 필드:
      - subwayId: 지하철 호선 ID(예: 1002=2호선).
      - updnLine: 상하행선 구분(상행/내선 · 하행/외선).
      - trainLineNm: 도착지(방면) 노선명(예: "성수행 - 구의방면").
      - statnNm: 지하철역명.
      - arvlMsg2: 첫 번째 도착 메시지(예: "전역 출발", "[2]번째 전역").
      - arvlMsg3: 두 번째 도착 메시지(현재 열차 위치, 예: "교대").
      - arvlCd: 도착 코드(0 진입,1 도착,2 출발,3 전역출발,4 전역진입,5 전역도착,99 운행중).
      - btrainSttus: 열차 종류(급행·일반 등).
      - bstatnNm: 종착(목적지) 지하철역명.
      - recptnDt: 열차 도착정보를 **생성한 시각**(과거 시각 — 현재와의 차를 보정해야 함).
      - barvlDt: 열차 도착 예정 시각(초). "0"이면 미정/도착.
      - ordkey: 정렬 키(상하행·열차순번 인코딩).
    값은 전부 문자열. 출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    subwayId: str | None = None
    updnLine: str | None = None
    trainLineNm: str | None = None
    statnNm: str | None = None
    arvlMsg2: str | None = None
    arvlMsg3: str | None = None
    arvlCd: str | None = None
    btrainSttus: str | None = None
    bstatnNm: str | None = None
    recptnDt: str | None = None
    barvlDt: str | None = None
    ordkey: str | None = None


class SubwayResponse(BaseModel):
    """지하철 실시간 도착 전체 응답 봉투 `{errorMessage, realtimeArrivalList}`.

    출처: https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    errorMessage: SubwayErrorMessage | None = None
    realtimeArrivalList: list[SubwayArrival] = []


# ─── 따릉이 응답 모델 ──────────────────────────────────────
# 봉투(정상): {"rentBikeStatus":{"list_total_count":N, "RESULT":{"CODE":"INFO-000",
#   "MESSAGE":"정상 처리되었습니다."}, "row":[{...}]}}.
# 인증키/요청오류는 최상위 {"RESULT":{"CODE":"INFO-100"/"ERROR-336",...}} 형태로 올 수 있다
# (서비스명 래퍼 없이) — 그래서 _result에서 양쪽을 모두 본다.
# 값은 전부 **문자열**(거치수·위경도 포함). extra="ignore".
# 출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do


class Result(BaseModel):
    """공통 결과 객체 `{CODE, MESSAGE}`.

    CODE != INFO-000이면 에러(인증키·요청·서버). 출처: 서울 OpenAPI 공통 결과코드표.
    """

    model_config = {"extra": "ignore"}

    CODE: str | None = None
    MESSAGE: str | None = None


class BikeStation(BaseModel):
    """따릉이 실시간 대여소 항목(부분).

    공식 필드:
      - rackTotCnt: 거치대 개수.
      - stationName: 대여소 이름(예: "102. 망원역 1번출구 앞").
      - parkingBikeTotCnt: 거치(주차)된 자전거 총 건수 = 대여 가능 수.
      - shared: 거치율(%).
      - stationLatitude / stationLongitude: 위도 / 경도.
      - stationId: 대여소 ID(예: "ST-4").
    값은 전부 문자열. 출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    rackTotCnt: str | None = None
    stationName: str | None = None
    parkingBikeTotCnt: str | None = None
    shared: str | None = None
    stationLatitude: str | None = None
    stationLongitude: str | None = None
    stationId: str | None = None


class BikeStatus(BaseModel):
    """따릉이 `rentBikeStatus` 봉투(list_total_count + RESULT + row).

    출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    list_total_count: int | None = None
    RESULT: Result | None = None
    row: list[BikeStation] = []


class BikeResponse(BaseModel):
    """따릉이 전체 응답 봉투 `{rentBikeStatus:{...}}`(또는 최상위 RESULT 에러).

    정상: rentBikeStatus가 채워진다. 인증키/요청 에러는 최상위 RESULT로 올 수 있다.
    출처: https://data.seoul.go.kr/dataList/OA-15493/A/1/datasetView.do
    """

    model_config = {"extra": "ignore"}

    rentBikeStatus: BikeStatus | None = None
    RESULT: Result | None = None
