"""에어코리아(한국환경공단) 대기오염정보 읽기 계약(contract).

상류 API의 '진실'만 담는다 — 엔드포인트 상수, 쿼리 제약/빌더, 응답 봉투/항목 모델.
MCP/네트워크 무의존(순수 상수 + pydantic 모델).

전부 GET·읽기. 인증은 **서비스키 필수**(data.go.kr 발급) — OAuth가 아니라 **쿼리 파라미터
`serviceKey`**다(헤더 아님). 응답은 기본 XML일 수 있어 **`returnType=json`을 명시**한다.
페이지네이션/건수는 응답 **본문**(`response.body.totalCount/pageNo/numOfRows`)에 실리므로
코어 `get_json`만으로 충분하다(헤더 동사 불필요).

⚠️ data.go.kr 서비스키 함정: 키는 **Encoding/Decoding 2종**으로 발급된다. httpx가 쿼리
파라미터를 자동 URL-인코딩하므로, params에는 **Decoding 키(원문)**를 넣어 이중 인코딩을 피한다.

출처(공식 — data.go.kr):
  - 대기오염정보 OpenAPI(ArpltnInforInqireSvc) 상세:
    https://www.data.go.kr/data/15073861/openapi.do
  - base URL `http://apis.data.go.kr/B552584/ArpltnInforInqireSvc`,
    공통 파라미터(serviceKey·returnType·numOfRows·pageNo), 봉투 구조,
    예보(getMinuDustFrcstDspth) 파라미터/필드는 위 페이지에서 확인.
"""

from __future__ import annotations

from pydantic import BaseModel

from arcsolve.services._datagokr import clamp_paging

# ─── base URL / 엔드포인트 상수 ─────────────────────────────
# 출처(base·엔드포인트): https://www.data.go.kr/data/15073861/openapi.do
BASE_URL = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc"
# 시도별 실시간 측정정보 조회
PATH_REALTIME_BY_REGION = "/getCtprvnRltmMesureDnsty"
# 측정소별 실시간 측정정보 조회
PATH_REALTIME_BY_STATION = "/getMsrstnAcctoRltmMesureDnsty"
# 대기질 예보통보 조회
PATH_FORECAST = "/getMinuDustFrcstDspth"


# ─── 쿼리 파라미터 제약(공식) ───────────────────────────────
# 공통 파라미터명. 출처: https://www.data.go.kr/data/15073861/openapi.do
PARAM_SERVICE_KEY = "serviceKey"
PARAM_RETURN_TYPE = "returnType"
PARAM_NUM_OF_ROWS = "numOfRows"
PARAM_PAGE_NO = "pageNo"
PARAM_SIDO_NAME = "sidoName"
PARAM_VER = "ver"
PARAM_STATION_NAME = "stationName"
PARAM_DATA_TERM = "dataTerm"
PARAM_SEARCH_DATE = "searchDate"
PARAM_INFORM_CODE = "informCode"

# returnType=json을 명시하지 않으면 상류가 XML을 줄 수 있다(get_json이 파싱 못함).
RETURN_TYPE_JSON = "json"

# 공통 페이지네이션 기본값. 출처: 위 페이지(numOfRows 기본 100, pageNo 기본 1).
DEFAULT_NUM_OF_ROWS = 100
DEFAULT_PAGE_NO = 1
# numOfRows/pageNo 안전 범위. pageNo는 1 이상, numOfRows는 1 이상.
# TODO(provenance): 상세 페이지에 numOfRows 상한이 인라인 명시되지 않아, data.go.kr 게이트웨이
#   통용 상한 9999를 보수적 상한으로 둔다(위반 시 결과코드 10 방지 — 과도값 클램프). 하한 1.
MAX_NUM_OF_ROWS = 9999
MIN_NUM_OF_ROWS = 1

# 시도별 조회 sidoName 허용값(전국 + 17개 광역시·도).
# 출처: data.go.kr 기술문서(ArpltnInforInqireSvc 시도별 실시간 측정정보). 라이브에서 통용.
SIDO_NAMES = (
    "전국",
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
    "세종",
)

# 측정소별 조회 dataTerm 허용값(요청 기간).
# 출처: data.go.kr 기술문서(측정소별 실시간 측정정보 — dataTerm DAILY/MONTH/3MONTH).
DATA_TERMS = ("DAILY", "MONTH", "3MONTH")
DEFAULT_DATA_TERM = "DAILY"

# 시도별 조회 ver(버전)별 노출 필드가 확장된다.
#   1.0(기본): so2/co/o3/no2/pm10 + 통합지수(khai)  · 1.3: pm25 포함  · 1.4: pm10/pm25 24시간 예측이동평균(pm10Value24/pm25Value24)
# 우리는 pm2.5까지 받기 위해 기본 1.3을 쓴다.
# 출처: data.go.kr 기술문서(시도별 실시간 측정정보 — ver 파라미터).
# TODO(provenance): ver별 정확한 필드 추가 범위(1.1/1.2/1.5/1.6 세부)는 공식 기술문서(다운로드 zip)에만 표로
#   있어 인라인 확인 불가 — 응답 모델은 extra="ignore"로 느슨히 받아 버전차를 흡수한다.
DEFAULT_VER = "1.3"

# 정상 응답 결과코드. 출처: data.go.kr(공통 OpenAPI 에러코드 규약 + 위 페이지 응답 header).
RESULT_CODE_OK = "00"


def build_realtime_by_region_params(
    *,
    sido_name: str,
    service_key: str,
    ver: str = DEFAULT_VER,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """시도별 실시간 측정정보(getCtprvnRltmMesureDnsty) 쿼리스트링을 만든다.

    serviceKey는 **Decoding 키 원문**을 넣는다(httpx가 자동 인코딩 → 이중 인코딩 방지).
    returnType=json을 항상 명시한다(기본 XML 회피).
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15073861/openapi.do
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    return {
        PARAM_SERVICE_KEY: service_key,
        PARAM_RETURN_TYPE: RETURN_TYPE_JSON,
        PARAM_SIDO_NAME: sido_name,
        PARAM_VER: ver,
        PARAM_NUM_OF_ROWS: num_of_rows,
        PARAM_PAGE_NO: page_no,
    }


def build_realtime_by_station_params(
    *,
    station_name: str,
    service_key: str,
    data_term: str = DEFAULT_DATA_TERM,
    ver: str = DEFAULT_VER,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """측정소별 실시간 측정정보(getMsrstnAcctoRltmMesureDnsty) 쿼리스트링을 만든다.

    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15073861/openapi.do
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    return {
        PARAM_SERVICE_KEY: service_key,
        PARAM_RETURN_TYPE: RETURN_TYPE_JSON,
        PARAM_STATION_NAME: station_name,
        PARAM_DATA_TERM: data_term,
        PARAM_VER: ver,
        PARAM_NUM_OF_ROWS: num_of_rows,
        PARAM_PAGE_NO: page_no,
    }


def build_forecast_params(
    *,
    search_date: str,
    service_key: str,
    inform_code: str | None = None,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    page_no: int = DEFAULT_PAGE_NO,
) -> dict[str, str | int]:
    """대기질 예보통보(getMinuDustFrcstDspth) 쿼리스트링을 만든다.

    searchDate는 `YYYY-MM-DD`. informCode(PM10/PM25/O3)는 선택(없으면 전체).
    numOfRows/pageNo는 공유 헬퍼로 안전 범위로 클램프한다.
    출처: https://www.data.go.kr/data/15073861/openapi.do
    """
    num_of_rows, page_no = clamp_paging(num_of_rows, page_no, max_rows=MAX_NUM_OF_ROWS)
    params: dict[str, str | int] = {
        PARAM_SERVICE_KEY: service_key,
        PARAM_RETURN_TYPE: RETURN_TYPE_JSON,
        PARAM_SEARCH_DATE: search_date,
        PARAM_NUM_OF_ROWS: num_of_rows,
        PARAM_PAGE_NO: page_no,
    }
    if inform_code:
        params[PARAM_INFORM_CODE] = inform_code
    return params


# ─── 응답 모델 ──────────────────────────────────────────────
# 봉투: {"response": {"header": {"resultCode","resultMsg"}, "body": {"items":[...],
#        "totalCount","pageNo","numOfRows"}}}.
# 측정값은 **문자열**로 온다("-"=결측). 그래서 수치 필드도 str | None로 받는다(캐스팅 금지).
# extra="ignore"로 느슨히(ver/operation별 필드차 흡수).
# 출처: https://www.data.go.kr/data/15073861/openapi.do


class Header(BaseModel):
    """응답 헤더 봉투 `{resultCode, resultMsg}`.

    resultCode != "00"이면 에러(서비스키 오류 등). 출처: 위 페이지 응답 header.
    """

    model_config = {"extra": "ignore"}

    resultCode: str | None = None
    resultMsg: str | None = None


class RealtimeMeasurement(BaseModel):
    """시도별·측정소별 실시간 측정 항목(부분).

    측정값(soVvalue 등)·통합지수(khaiValue)·등급(*Grade)은 전부 **문자열**이며 결측은 "-".
    24시간 예측이동농도(pm10Value24/pm25Value24)는 ver≥1.4에서만 채워진다.
    공식 필드: dataTime · mangName(측정망: 도시대기 등) · sidoName(시도별) ·
      stationName(측정소별) · so2Value/coValue/o3Value/no2Value/pm10Value/pm25Value ·
      khaiValue(통합대기환경지수)/khaiGrade · *Grade(1좋음~4매우나쁨) · pm10Value24/pm25Value24.
    출처: https://www.data.go.kr/data/15073861/openapi.do
    """

    model_config = {"extra": "ignore"}

    dataTime: str | None = None
    mangName: str | None = None
    sidoName: str | None = None
    stationName: str | None = None
    so2Value: str | None = None
    coValue: str | None = None
    o3Value: str | None = None
    no2Value: str | None = None
    pm10Value: str | None = None
    pm25Value: str | None = None
    pm10Value24: str | None = None
    pm25Value24: str | None = None
    khaiValue: str | None = None
    khaiGrade: str | None = None
    so2Grade: str | None = None
    coGrade: str | None = None
    o3Grade: str | None = None
    no2Grade: str | None = None
    pm10Grade: str | None = None
    pm25Grade: str | None = None


class ForecastItem(BaseModel):
    """대기질 예보통보 항목(부분).

    공식 필드: dataTime(발표시각) · informCode(PM10/PM25/O3) · informData(예보일) ·
      informOverall(예보 개황) · informCause(발생 원인) · informGrade(권역별 등급) ·
      actionKnack(행동요령) · imageUrl1~9(예측 모델 이미지).
    출처: https://www.data.go.kr/data/15073861/openapi.do
    """

    model_config = {"extra": "ignore"}

    dataTime: str | None = None
    informCode: str | None = None
    informData: str | None = None
    informOverall: str | None = None
    informCause: str | None = None
    informGrade: str | None = None
    actionKnack: str | None = None


class RealtimeBody(BaseModel):
    """실시간 측정 응답 body 봉투(items + 페이지네이션).

    출처: https://www.data.go.kr/data/15073861/openapi.do
    """

    model_config = {"extra": "ignore"}

    items: list[RealtimeMeasurement] = []
    totalCount: int | None = None
    pageNo: int | None = None
    numOfRows: int | None = None


class ForecastBody(BaseModel):
    """예보통보 응답 body 봉투(items + 페이지네이션)."""

    model_config = {"extra": "ignore"}

    items: list[ForecastItem] = []
    totalCount: int | None = None
    pageNo: int | None = None
    numOfRows: int | None = None


class RealtimeResponse(BaseModel):
    """실시간 측정 전체 응답 봉투 `{response:{header, body}}`."""

    model_config = {"extra": "ignore"}

    header: Header | None = None
    body: RealtimeBody | None = None


class ForecastResponse(BaseModel):
    """예보통보 전체 응답 봉투 `{response:{header, body}}`."""

    model_config = {"extra": "ignore"}

    header: Header | None = None
    body: ForecastBody | None = None
